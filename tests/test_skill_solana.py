"""Tests for the Solana skill."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "my_digital_being"))

from skills.skill_solana import (
    SolanaSkill,
    TransferResult,
    StakeResult,
    StakeAccountInfo,
    NFTMetadata,
    NFTTransferResult,
    SwapQuote,
    SwapResult,
    TokenBalance,
    SOL_MINT,
    USDC_MINT,
    USDT_MINT,
    MSOL_MINT,
    STAKE_PROGRAM_ID,
    TOKEN_METADATA_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
    LAMPORTS_PER_SOL,
    solana_skill,
)


class TestConstants:
    """Test that all required constants are defined correctly."""

    def test_sol_mint(self):
        assert SOL_MINT == "So11111111111111111111111111111111111111112"

    def test_usdc_mint(self):
        assert USDC_MINT == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    def test_usdt_mint(self):
        assert USDT_MINT == "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

    def test_msol_mint(self):
        assert MSOL_MINT == "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"

    def test_stake_program_id(self):
        assert STAKE_PROGRAM_ID == "Stake11111111111111111111111111111111111111"

    def test_token_metadata_program_id(self):
        assert TOKEN_METADATA_PROGRAM_ID == "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

    def test_token_program_id(self):
        assert TOKEN_PROGRAM_ID == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

    def test_associated_token_program_id(self):
        assert ASSOCIATED_TOKEN_PROGRAM_ID == "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

    def test_lamports_per_sol(self):
        assert LAMPORTS_PER_SOL == 1_000_000_000


class TestTransferResult:
    """Test TransferResult dataclass."""

    def test_create_success_result(self):
        result = TransferResult(
            success=True,
            signature="abc123",
            amount=1.5,
            recipient="someaddress"
        )
        assert result.success is True
        assert result.signature == "abc123"
        assert result.amount == 1.5
        assert result.recipient == "someaddress"
        assert result.error is None

    def test_create_error_result(self):
        result = TransferResult(
            success=False,
            error="Transfer failed"
        )
        assert result.success is False
        assert result.error == "Transfer failed"
        assert result.signature is None

    def test_default_values(self):
        result = TransferResult(success=True)
        assert result.signature is None
        assert result.error is None
        assert result.amount is None
        assert result.recipient is None


class TestStakeResult:
    """Test StakeResult dataclass."""

    def test_create_success_result(self):
        result = StakeResult(
            success=True,
            signature="stake123",
            stake_account="stakeaccount123",
            amount_lamports=1_000_000_000
        )
        assert result.success is True
        assert result.signature == "stake123"
        assert result.stake_account == "stakeaccount123"
        assert result.amount_lamports == 1_000_000_000
        assert result.error is None

    def test_create_error_result(self):
        result = StakeResult(
            success=False,
            error="Staking failed"
        )
        assert result.success is False
        assert result.error == "Staking failed"

    def test_default_values(self):
        result = StakeResult(success=True)
        assert result.signature is None
        assert result.stake_account is None
        assert result.error is None
        assert result.amount_lamports is None


class TestStakeAccountInfo:
    """Test StakeAccountInfo dataclass."""

    def test_create_full(self):
        info = StakeAccountInfo(
            address="stakeaddr123",
            lamports=2_000_000_000,
            state="delegated",
            voter="voter123",
            activation_epoch=100,
            deactivation_epoch=None
        )
        assert info.address == "stakeaddr123"
        assert info.lamports == 2_000_000_000
        assert info.state == "delegated"
        assert info.voter == "voter123"
        assert info.activation_epoch == 100
        assert info.deactivation_epoch is None

    def test_create_minimal(self):
        info = StakeAccountInfo(
            address="stakeaddr123",
            lamports=1_000_000_000,
            state="inactive"
        )
        assert info.address == "stakeaddr123"
        assert info.lamports == 1_000_000_000
        assert info.state == "inactive"
        assert info.voter is None


class TestNFTMetadata:
    """Test NFTMetadata dataclass."""

    def test_create_full(self):
        metadata = NFTMetadata(
            mint="nftmint123",
            name="Cool NFT",
            symbol="COOL",
            uri="https://example.com/metadata.json",
            image="https://example.com/image.png",
            description="A cool NFT",
            collection="cool_collection",
            attributes=[{"trait_type": "rarity", "value": "rare"}]
        )
        assert metadata.mint == "nftmint123"
        assert metadata.name == "Cool NFT"
        assert metadata.symbol == "COOL"
        assert metadata.uri == "https://example.com/metadata.json"
        assert metadata.image == "https://example.com/image.png"
        assert metadata.description == "A cool NFT"
        assert metadata.collection == "cool_collection"
        assert len(metadata.attributes) == 1

    def test_create_minimal(self):
        metadata = NFTMetadata(
            mint="nftmint123",
            name="Basic NFT",
            symbol="BASIC",
            uri=""
        )
        assert metadata.mint == "nftmint123"
        assert metadata.name == "Basic NFT"
        assert metadata.image is None
        assert metadata.description is None
        assert metadata.collection is None
        assert metadata.attributes == []

    def test_attributes_default_factory(self):
        metadata1 = NFTMetadata(mint="a", name="A", symbol="A", uri="")
        metadata2 = NFTMetadata(mint="b", name="B", symbol="B", uri="")
        metadata1.attributes.append("test")
        assert len(metadata2.attributes) == 0


class TestNFTTransferResult:
    """Test NFTTransferResult dataclass."""

    def test_create_success_result(self):
        result = NFTTransferResult(
            success=True,
            signature="nfttx123",
            mint="nftmint123",
            recipient="recipient123"
        )
        assert result.success is True
        assert result.signature == "nfttx123"
        assert result.mint == "nftmint123"
        assert result.recipient == "recipient123"
        assert result.error is None

    def test_create_error_result(self):
        result = NFTTransferResult(
            success=False,
            error="NFT not found",
            mint="nftmint123",
            recipient="recipient123"
        )
        assert result.success is False
        assert result.error == "NFT not found"
        assert result.mint == "nftmint123"

    def test_default_values(self):
        result = NFTTransferResult(success=True)
        assert result.signature is None
        assert result.error is None
        assert result.mint is None
        assert result.recipient is None


class TestSwapQuote:
    """Test SwapQuote dataclass."""

    def test_create(self):
        quote = SwapQuote(
            input_mint=SOL_MINT,
            output_mint=USDC_MINT,
            in_amount=1_000_000_000,
            out_amount=100_000_000,
            price_impact_pct=0.01,
            route_plan=[],
            raw_response={}
        )
        assert quote.input_mint == SOL_MINT
        assert quote.output_mint == USDC_MINT
        assert quote.in_amount == 1_000_000_000
        assert quote.out_amount == 100_000_000


class TestSwapResult:
    """Test SwapResult dataclass."""

    def test_create_success(self):
        result = SwapResult(
            success=True,
            signature="swap123",
            in_amount=1_000_000_000,
            out_amount=100_000_000
        )
        assert result.success is True
        assert result.signature == "swap123"

    def test_create_error(self):
        result = SwapResult(success=False, error="Swap failed")
        assert result.success is False
        assert result.error == "Swap failed"


class TestSolanaSkillInitialization:
    """Test SolanaSkill requires initialization."""

    def test_skill_instance_exists(self):
        assert solana_skill is not None
        assert isinstance(solana_skill, SolanaSkill)

    def test_skill_name(self):
        skill = SolanaSkill()
        assert skill.skill_name == "solana"

    def test_required_api_keys(self):
        skill = SolanaSkill()
        assert "SOLANA_PRIVATE_KEY" in skill.required_api_keys

    def test_optional_api_keys(self):
        skill = SolanaSkill()
        assert "SOLANA_RPC_URL" in skill.optional_api_keys
        assert "HELIUS_API_KEY" in skill.optional_api_keys

    def test_not_initialized_by_default(self):
        skill = SolanaSkill()
        assert skill._initialized is False

    def test_wallet_address_none_before_init(self):
        skill = SolanaSkill()
        assert skill.wallet_address is None


class TestSolanaSkillMethodsRequireInit:
    """Test that methods raise RuntimeError when not initialized."""

    @pytest.fixture
    def uninitialized_skill(self):
        return SolanaSkill()

    @pytest.mark.asyncio
    async def test_get_sol_balance_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_sol_balance()

    @pytest.mark.asyncio
    async def test_get_token_balances_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_token_balances()

    @pytest.mark.asyncio
    async def test_get_token_price_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_token_price(SOL_MINT)

    @pytest.mark.asyncio
    async def test_get_swap_quote_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_swap_quote(
                SOL_MINT, USDC_MINT, 1_000_000_000
            )

    @pytest.mark.asyncio
    async def test_execute_swap_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.execute_swap(
                SOL_MINT, USDC_MINT, 1_000_000_000
            )

    @pytest.mark.asyncio
    async def test_transfer_sol_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.transfer_sol("recipient", 1.0)

    @pytest.mark.asyncio
    async def test_transfer_spl_token_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.transfer_spl_token(USDC_MINT, "recipient", 1.0)

    @pytest.mark.asyncio
    async def test_stake_sol_native_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.stake_sol_native(1.0, "validator")

    @pytest.mark.asyncio
    async def test_stake_sol_marinade_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.stake_sol_marinade(1.0)

    @pytest.mark.asyncio
    async def test_unstake_marinade_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.unstake_marinade(1.0)

    @pytest.mark.asyncio
    async def test_get_stake_accounts_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_stake_accounts()

    @pytest.mark.asyncio
    async def test_get_nfts_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_nfts()

    @pytest.mark.asyncio
    async def test_transfer_nft_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.transfer_nft("mint", "recipient")

    @pytest.mark.asyncio
    async def test_get_nft_floor_price_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_nft_floor_price("collection")

    @pytest.mark.asyncio
    async def test_get_recent_transactions_requires_init(self, uninitialized_skill):
        with pytest.raises(RuntimeError, match="Skill not initialized"):
            await uninitialized_skill.get_recent_transactions()
