"""Activity for transferring SOL and SPL tokens on Solana."""

import logging
import re
from typing import Any, Dict, Optional

from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_solana import solana_skill, SOL_MINT, LAMPORTS_PER_SOL

logger = logging.getLogger(__name__)

SOLANA_ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
SOLSCAN_TX_URL = "https://solscan.io/tx/"


def is_valid_solana_address(address: str) -> bool:
    """Validate a Solana address format."""
    if not address or not isinstance(address, str):
        return False
    return bool(SOLANA_ADDRESS_PATTERN.match(address))


@activity(
    name="transfer_tokens",
    energy_cost=0.3,
    cooldown=30,
    required_skills=["solana"],
)
class TransferTokensActivity(ActivityBase):
    """
    Transfer SOL or SPL tokens to another wallet.

    Reads from shared_data:
        - transfer_recipient: Destination wallet address (required)
        - transfer_amount: Amount to send (required)
        - transfer_mint: Token mint address (optional, defaults to SOL)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the token transfer."""
        try:
            logger.info("Starting token transfer activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            transfer_data = shared_data.get_category_data("transfer") or {}
            recipient = transfer_data.get("transfer_recipient")
            amount = transfer_data.get("transfer_amount")
            mint = transfer_data.get("transfer_mint")

            if not recipient:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: transfer_recipient"
                )

            if amount is None:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: transfer_amount"
                )

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return ActivityResult(
                    success=False,
                    error=f"Invalid amount: {amount}"
                )

            if amount <= 0:
                return ActivityResult(
                    success=False,
                    error="Amount must be greater than zero"
                )

            if not is_valid_solana_address(recipient):
                return ActivityResult(
                    success=False,
                    error=f"Invalid recipient address format: {recipient}"
                )

            is_sol_transfer = mint is None or mint == SOL_MINT

            if is_sol_transfer:
                balance = await solana_skill.get_sol_balance()
                token_symbol = "SOL"

                if balance < amount + 0.001:
                    return ActivityResult(
                        success=False,
                        error=f"Insufficient SOL balance: {balance:.4f} SOL "
                              f"(need {amount} + fees)"
                    )

                result = await solana_skill.transfer_sol(recipient, amount)
            else:
                if not is_valid_solana_address(mint):
                    return ActivityResult(
                        success=False,
                        error=f"Invalid mint address format: {mint}"
                    )

                token_balances = await solana_skill.get_token_balances()
                token_balance = None
                token_symbol = mint[:8] + "..."

                for tb in token_balances:
                    if tb.mint == mint:
                        token_balance = tb.ui_amount
                        token_symbol = tb.symbol
                        break

                if token_balance is None:
                    return ActivityResult(
                        success=False,
                        error=f"Token {mint} not found in wallet"
                    )

                if token_balance < amount:
                    return ActivityResult(
                        success=False,
                        error=f"Insufficient {token_symbol} balance: "
                              f"{token_balance} (need {amount})"
                    )

                result = await solana_skill.transfer_spl_token(mint, recipient, amount)

            if not result.success:
                logger.error(f"Transfer failed: {result.error}")
                return ActivityResult(
                    success=False,
                    error=result.error
                )

            explorer_url = f"{SOLSCAN_TX_URL}{result.signature}"
            logger.info(f"Transfer successful: {result.signature}")

            return ActivityResult(
                success=True,
                data={
                    "signature": result.signature,
                    "recipient": recipient,
                    "amount": amount,
                    "token": token_symbol,
                    "explorer_url": explorer_url,
                },
                metadata={
                    "summary": f"Transferred {amount} {token_symbol} to "
                               f"{recipient[:8]}...{recipient[-4:]}"
                }
            )

        except Exception as e:
            logger.error(f"Transfer activity failed: {e}")
            return ActivityResult(success=False, error=str(e))
