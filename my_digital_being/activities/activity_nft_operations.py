"""Activities for NFT operations on Solana."""

import logging
import re
from typing import Any, Dict, List, Optional

from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_solana import solana_skill, LAMPORTS_PER_SOL

logger = logging.getLogger(__name__)

SOLANA_ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
SOLSCAN_TX_URL = "https://solscan.io/tx/"
SOLSCAN_TOKEN_URL = "https://solscan.io/token/"


def is_valid_solana_address(address: str) -> bool:
    """Validate a Solana address format."""
    if not address or not isinstance(address, str):
        return False
    return bool(SOLANA_ADDRESS_PATTERN.match(address))


@activity(
    name="get_nft_collection",
    energy_cost=0.2,
    cooldown=300,
    required_skills=["solana"],
)
class GetNFTCollectionActivity(ActivityBase):
    """
    Fetch all NFTs owned by a wallet with metadata.

    Reads from shared_data:
        - nft_wallet_address: Wallet address to check (optional, defaults to skill wallet)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the NFT collection fetch."""
        try:
            logger.info("Starting NFT collection fetch activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            nft_data = shared_data.get_category_data("nft") or {}
            wallet_address = nft_data.get("nft_wallet_address")

            if wallet_address and not is_valid_solana_address(wallet_address):
                return ActivityResult(
                    success=False,
                    error=f"Invalid wallet address format: {wallet_address}"
                )

            nfts = await solana_skill.get_nfts(wallet_address)

            nft_list = []
            collections = {}

            for nft in nfts:
                nft_entry = {
                    "mint": nft.mint,
                    "name": nft.name,
                    "symbol": nft.symbol,
                    "image": nft.image,
                    "description": nft.description,
                    "collection": nft.collection,
                    "attributes": nft.attributes,
                    "uri": nft.uri,
                }
                nft_list.append(nft_entry)

                collection_key = nft.collection or "Unknown"
                if collection_key not in collections:
                    collections[collection_key] = 0
                collections[collection_key] += 1

            wallet_display = wallet_address or solana_skill.wallet_address
            logger.info(f"Found {len(nfts)} NFTs in wallet {wallet_display}")

            if nfts:
                collection_summary = ", ".join(
                    f"{count} {name}" for name, count in
                    sorted(collections.items(), key=lambda x: -x[1])[:3]
                )
                summary = f"Found {len(nfts)} NFTs: {collection_summary}"
            else:
                summary = "No NFTs found in wallet"

            return ActivityResult(
                success=True,
                data={
                    "nfts": nft_list,
                    "nft_count": len(nfts),
                    "collections": collections,
                    "wallet_address": wallet_display,
                },
                metadata={
                    "summary": summary
                }
            )

        except Exception as e:
            logger.error(f"NFT collection fetch failed: {e}")
            return ActivityResult(success=False, error=str(e))


@activity(
    name="transfer_nft",
    energy_cost=0.4,
    cooldown=60,
    required_skills=["solana"],
)
class TransferNFTActivity(ActivityBase):
    """
    Transfer an NFT to another wallet.

    Reads from shared_data:
        - nft_mint: Mint address of the NFT to transfer (required)
        - nft_recipient: Destination wallet address (required)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the NFT transfer."""
        try:
            logger.info("Starting NFT transfer activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            nft_data = shared_data.get_category_data("nft") or {}
            mint = nft_data.get("nft_mint")
            recipient = nft_data.get("nft_recipient")

            if not mint:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: nft_mint"
                )

            if not recipient:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: nft_recipient"
                )

            if not is_valid_solana_address(mint):
                return ActivityResult(
                    success=False,
                    error=f"Invalid NFT mint address format: {mint}"
                )

            if not is_valid_solana_address(recipient):
                return ActivityResult(
                    success=False,
                    error=f"Invalid recipient address format: {recipient}"
                )

            owned_nfts = await solana_skill.get_nfts()
            nft_owned = False
            nft_name = "Unknown NFT"

            for nft in owned_nfts:
                if nft.mint == mint:
                    nft_owned = True
                    nft_name = nft.name
                    break

            if not nft_owned:
                return ActivityResult(
                    success=False,
                    error=f"NFT {mint} not found in wallet. Cannot transfer."
                )

            result = await solana_skill.transfer_nft(mint, recipient)

            if not result.success:
                logger.error(f"NFT transfer failed: {result.error}")
                return ActivityResult(success=False, error=result.error)

            explorer_url = f"{SOLSCAN_TX_URL}{result.signature}"
            logger.info(f"NFT transfer successful: {result.signature}")

            return ActivityResult(
                success=True,
                data={
                    "signature": result.signature,
                    "mint": mint,
                    "nft_name": nft_name,
                    "recipient": recipient,
                    "explorer_url": explorer_url,
                },
                metadata={
                    "summary": f"Transferred '{nft_name}' to {recipient[:8]}...{recipient[-4:]}"
                }
            )

        except Exception as e:
            logger.error(f"NFT transfer activity failed: {e}")
            return ActivityResult(success=False, error=str(e))


@activity(
    name="check_nft_floor_prices",
    energy_cost=0.1,
    cooldown=600,
    required_skills=["solana"],
)
class CheckNFTFloorPricesActivity(ActivityBase):
    """
    Get floor prices for NFT collections.

    Reads from shared_data:
        - nft_collections: List of collection symbols to check (optional)
        - check_owned: If true, check floor prices for owned collections (default: true)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the floor price check."""
        try:
            logger.info("Starting NFT floor price check activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            nft_data = shared_data.get_category_data("nft") or {}
            collections_to_check = nft_data.get("nft_collections", [])
            check_owned = nft_data.get("check_owned", True)

            if check_owned:
                owned_nfts = await solana_skill.get_nfts()

                owned_collections = set()
                for nft in owned_nfts:
                    if nft.collection:
                        owned_collections.add(nft.collection)
                    elif nft.symbol:
                        owned_collections.add(nft.symbol.lower())

                for col in owned_collections:
                    if col not in collections_to_check:
                        collections_to_check.append(col)

            if not collections_to_check:
                return ActivityResult(
                    success=True,
                    data={
                        "floor_prices": {},
                        "collections_checked": 0,
                    },
                    metadata={
                        "summary": "No collections to check for floor prices"
                    }
                )

            floor_prices = {}
            errors = []

            for collection in collections_to_check:
                try:
                    price = await solana_skill.get_nft_floor_price(collection)
                    if price is not None:
                        floor_prices[collection] = price
                    else:
                        errors.append(f"No price data for {collection}")
                except Exception as e:
                    errors.append(f"Error fetching {collection}: {str(e)}")

            logger.info(f"Fetched floor prices for {len(floor_prices)} collections")

            if floor_prices:
                price_summary = ", ".join(
                    f"{col}: {price:.2f} SOL"
                    for col, price in sorted(
                        floor_prices.items(),
                        key=lambda x: -x[1]
                    )[:3]
                )
                summary = f"Floor prices: {price_summary}"
            else:
                summary = "No floor price data available"

            return ActivityResult(
                success=True,
                data={
                    "floor_prices": floor_prices,
                    "collections_checked": len(collections_to_check),
                    "errors": errors if errors else None,
                },
                metadata={
                    "summary": summary
                }
            )

        except Exception as e:
            logger.error(f"Floor price check failed: {e}")
            return ActivityResult(success=False, error=str(e))


@activity(
    name="analyze_nft_portfolio",
    energy_cost=0.3,
    cooldown=1800,
    required_skills=["solana"],
)
class AnalyzeNFTPortfolioActivity(ActivityBase):
    """
    Full portfolio analysis combining NFT holdings with floor price valuations.
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the NFT portfolio analysis."""
        try:
            logger.info("Starting NFT portfolio analysis activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            nfts = await solana_skill.get_nfts()

            if not nfts:
                return ActivityResult(
                    success=True,
                    data={
                        "total_nfts": 0,
                        "total_value_sol": 0,
                        "collections": [],
                        "nfts_by_collection": {},
                    },
                    metadata={
                        "summary": "No NFTs in portfolio"
                    }
                )

            collections_map: Dict[str, List[Dict[str, Any]]] = {}

            for nft in nfts:
                collection_key = nft.collection or nft.symbol or "Unknown"

                if collection_key not in collections_map:
                    collections_map[collection_key] = []

                collections_map[collection_key].append({
                    "mint": nft.mint,
                    "name": nft.name,
                    "image": nft.image,
                })

            collection_analysis = []
            total_value_sol = 0.0
            valued_count = 0

            for collection_key, nft_list in collections_map.items():
                floor_price = None
                try:
                    floor_price = await solana_skill.get_nft_floor_price(collection_key)
                except Exception:
                    pass

                count = len(nft_list)
                collection_value = None

                if floor_price is not None:
                    collection_value = floor_price * count
                    total_value_sol += collection_value
                    valued_count += count

                collection_analysis.append({
                    "collection": collection_key,
                    "count": count,
                    "floor_price_sol": floor_price,
                    "total_value_sol": collection_value,
                    "nfts": nft_list,
                })

            collection_analysis.sort(
                key=lambda x: (x["total_value_sol"] or 0),
                reverse=True
            )

            sol_price = await solana_skill.get_token_price(
                "So11111111111111111111111111111111111111112"
            )
            total_value_usd = None
            if sol_price and total_value_sol > 0:
                total_value_usd = total_value_sol * sol_price

            logger.info(
                f"Portfolio analysis complete: {len(nfts)} NFTs, "
                f"~{total_value_sol:.2f} SOL value"
            )

            summary_parts = [f"{len(nfts)} NFTs in {len(collections_map)} collections"]
            if total_value_sol > 0:
                summary_parts.append(f"~{total_value_sol:.2f} SOL floor value")
                if total_value_usd:
                    summary_parts.append(f"(~${total_value_usd:.2f})")

            return ActivityResult(
                success=True,
                data={
                    "total_nfts": len(nfts),
                    "total_collections": len(collections_map),
                    "valued_nfts": valued_count,
                    "total_value_sol": total_value_sol,
                    "total_value_usd": total_value_usd,
                    "sol_price_usd": sol_price,
                    "collections": collection_analysis,
                },
                metadata={
                    "summary": " ".join(summary_parts)
                }
            )

        except Exception as e:
            logger.error(f"NFT portfolio analysis failed: {e}")
            return ActivityResult(success=False, error=str(e))
