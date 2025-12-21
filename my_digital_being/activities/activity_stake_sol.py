"""Activities for SOL staking operations on Solana."""

import logging
from typing import Any, Dict, List

from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_solana import (
    solana_skill,
    MSOL_MINT,
    LAMPORTS_PER_SOL,
)

logger = logging.getLogger(__name__)

SOLSCAN_TX_URL = "https://solscan.io/tx/"
SOLSCAN_ACCOUNT_URL = "https://solscan.io/account/"

RECOMMENDED_VALIDATORS = {
    "marinade": "mnde7j6kMb5Bn7DWGjMaXFhgPdLmNM9kKgLFmJ6x4g",
    "jito": "J1to1yufRnoWn81KYg1XkTWzmKjnYSnmE2VY8DGUJ9Qv",
    "helius": "heLiUSQ2ZFFXGXGX9Y7MGoP6q8rEVMBSXnZDPqpPuH5",
    "coinbase": "beefKGBWeSpHzYBHZXwp5So7wdQGX6mu4ZHCsH3uTar",
}


@activity(
    name="stake_sol",
    energy_cost=0.5,
    cooldown=3600,
    required_skills=["solana"],
)
class StakeSolActivity(ActivityBase):
    """
    Stake SOL using native staking or Marinade liquid staking.

    Reads from shared_data:
        - stake_amount: Amount of SOL to stake (required)
        - stake_method: "native" or "marinade" (required)
        - stake_validator: Validator vote account for native staking
                          (optional, defaults to Marinade validator)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the staking operation."""
        try:
            logger.info("Starting SOL staking activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            stake_data = shared_data.get_category_data("stake") or {}
            amount = stake_data.get("stake_amount")
            method = stake_data.get("stake_method", "marinade")
            validator = stake_data.get("stake_validator")

            if amount is None:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: stake_amount"
                )

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return ActivityResult(
                    success=False,
                    error=f"Invalid stake amount: {amount}"
                )

            if amount <= 0:
                return ActivityResult(
                    success=False,
                    error="Stake amount must be greater than zero"
                )

            method = method.lower()
            if method not in ("native", "marinade"):
                return ActivityResult(
                    success=False,
                    error=f"Invalid stake method: {method}. Use 'native' or 'marinade'"
                )

            balance = await solana_skill.get_sol_balance()
            required = amount + 0.01

            if balance < required:
                return ActivityResult(
                    success=False,
                    error=f"Insufficient SOL balance: {balance:.4f} SOL "
                          f"(need {amount} + fees)"
                )

            if method == "marinade":
                result = await solana_skill.stake_sol_marinade(amount)

                if not result.success:
                    logger.error(f"Marinade staking failed: {result.error}")
                    return ActivityResult(success=False, error=result.error)

                explorer_url = f"{SOLSCAN_TX_URL}{result.signature}"
                logger.info(f"Marinade stake successful: {result.signature}")

                return ActivityResult(
                    success=True,
                    data={
                        "signature": result.signature,
                        "method": "marinade",
                        "amount_sol": amount,
                        "token_received": "mSOL",
                        "explorer_url": explorer_url,
                    },
                    metadata={
                        "summary": f"Liquid staked {amount} SOL via Marinade for mSOL"
                    }
                )

            else:
                if not validator:
                    validator = RECOMMENDED_VALIDATORS["marinade"]

                result = await solana_skill.stake_sol_native(amount, validator)

                if not result.success:
                    logger.error(f"Native staking failed: {result.error}")
                    return ActivityResult(success=False, error=result.error)

                explorer_url = f"{SOLSCAN_TX_URL}{result.signature}"
                stake_account_url = f"{SOLSCAN_ACCOUNT_URL}{result.stake_account}"
                logger.info(
                    f"Native stake successful: {result.signature}, "
                    f"stake account: {result.stake_account}"
                )

                return ActivityResult(
                    success=True,
                    data={
                        "signature": result.signature,
                        "method": "native",
                        "amount_sol": amount,
                        "stake_account": result.stake_account,
                        "validator": validator,
                        "explorer_url": explorer_url,
                        "stake_account_url": stake_account_url,
                    },
                    metadata={
                        "summary": f"Natively staked {amount} SOL to validator "
                                   f"{validator[:8]}..."
                    }
                )

        except Exception as e:
            logger.error(f"Stake activity failed: {e}")
            return ActivityResult(success=False, error=str(e))


@activity(
    name="unstake_sol",
    energy_cost=0.3,
    cooldown=3600,
    required_skills=["solana"],
)
class UnstakeSolActivity(ActivityBase):
    """
    Unstake mSOL back to SOL via Marinade (instant unstake through Jupiter swap).

    Reads from shared_data:
        - unstake_amount: Amount of mSOL to unstake (required)
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the unstaking operation."""
        try:
            logger.info("Starting mSOL unstaking activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            stake_data = shared_data.get_category_data("stake") or {}
            amount = stake_data.get("unstake_amount")

            if amount is None:
                return ActivityResult(
                    success=False,
                    error="Missing required parameter: unstake_amount"
                )

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return ActivityResult(
                    success=False,
                    error=f"Invalid unstake amount: {amount}"
                )

            if amount <= 0:
                return ActivityResult(
                    success=False,
                    error="Unstake amount must be greater than zero"
                )

            token_balances = await solana_skill.get_token_balances()
            msol_balance = 0.0

            for tb in token_balances:
                if tb.mint == MSOL_MINT:
                    msol_balance = tb.ui_amount
                    break

            if msol_balance < amount:
                return ActivityResult(
                    success=False,
                    error=f"Insufficient mSOL balance: {msol_balance:.4f} mSOL "
                          f"(need {amount})"
                )

            result = await solana_skill.unstake_marinade(amount)

            if not result.success:
                logger.error(f"Unstaking failed: {result.error}")
                return ActivityResult(success=False, error=result.error)

            sol_received = (result.amount_lamports or 0) / LAMPORTS_PER_SOL
            explorer_url = f"{SOLSCAN_TX_URL}{result.signature}"
            logger.info(f"Unstake successful: {result.signature}")

            return ActivityResult(
                success=True,
                data={
                    "signature": result.signature,
                    "msol_amount": amount,
                    "sol_received": sol_received,
                    "explorer_url": explorer_url,
                },
                metadata={
                    "summary": f"Unstaked {amount} mSOL, received ~{sol_received:.4f} SOL"
                }
            )

        except Exception as e:
            logger.error(f"Unstake activity failed: {e}")
            return ActivityResult(success=False, error=str(e))


@activity(
    name="check_stake_accounts",
    energy_cost=0.1,
    cooldown=600,
    required_skills=["solana"],
)
class CheckStakeAccountsActivity(ActivityBase):
    """
    View all stake accounts and mSOL balance for the wallet.
    """

    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the stake account check."""
        try:
            logger.info("Starting stake account check activity")

            if not await solana_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to initialize Solana skill"
                )

            stake_accounts = await solana_skill.get_stake_accounts()

            token_balances = await solana_skill.get_token_balances()
            msol_balance = 0.0

            for tb in token_balances:
                if tb.mint == MSOL_MINT:
                    msol_balance = tb.ui_amount
                    break

            stake_accounts_data = []
            total_staked_lamports = 0

            for account in stake_accounts:
                stake_accounts_data.append({
                    "address": account.address,
                    "lamports": account.lamports,
                    "sol_amount": account.lamports / LAMPORTS_PER_SOL,
                    "state": account.state,
                    "voter": account.voter,
                    "activation_epoch": account.activation_epoch,
                    "deactivation_epoch": account.deactivation_epoch,
                })
                total_staked_lamports += account.lamports

            total_staked_sol = total_staked_lamports / LAMPORTS_PER_SOL

            logger.info(
                f"Found {len(stake_accounts)} stake accounts, "
                f"{total_staked_sol:.4f} SOL staked, "
                f"{msol_balance:.4f} mSOL balance"
            )

            summary_parts = []
            if stake_accounts:
                summary_parts.append(
                    f"{len(stake_accounts)} native stake accounts "
                    f"({total_staked_sol:.2f} SOL)"
                )
            if msol_balance > 0:
                summary_parts.append(f"{msol_balance:.4f} mSOL liquid staked")

            if not summary_parts:
                summary = "No active stakes found"
            else:
                summary = ", ".join(summary_parts)

            return ActivityResult(
                success=True,
                data={
                    "stake_accounts": stake_accounts_data,
                    "stake_account_count": len(stake_accounts),
                    "total_staked_sol": total_staked_sol,
                    "msol_balance": msol_balance,
                },
                metadata={
                    "summary": summary
                }
            )

        except Exception as e:
            logger.error(f"Stake account check failed: {e}")
            return ActivityResult(success=False, error=str(e))
