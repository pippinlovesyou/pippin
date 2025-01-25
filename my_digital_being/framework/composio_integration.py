"""
Composio integration module for managing OAuth flows and dynamic tool integration.
Implements:
 - handle_oauth_callback(...) to finalize the connection
 - store a connected indicator in _oauth_connections
 - list_available_integrations() returns "connected": True if we have that.
 - list_actions_for_app(...) returns the app's actions by calling Composio's API directly

[ADDED] We now persist these connections in ./storage/composio_oauth.json
"""

import os
import logging
import json
from pathlib import Path
from typing import Dict, Any, List

import requests  # Used for the direct Composio API call

from .secret_storage import secret_manager
from composio_openai import ComposioToolSet

logger = logging.getLogger(__name__)


class ComposioManager:
    def __init__(self):
        self._toolset = None
        self._entity_id = "MyDigitalBeing"
        self._oauth_connections: Dict[str, Dict[str, Any]] = {}
        self._available_apps: Dict[str, Any] = {}

        # [ADDED] We store the OAuth connections in a JSON file
        self.storage_file = Path("./storage/composio_oauth.json")

        logger.info("Starting Composio integration initialization...")

        # Load persisted OAuth connections if any
        self._load_persistence()

        # Initialize the Composio toolset
        self._initialize_toolset()

    # [ADDED] Load connections from disk
    def _load_persistence(self):
        if self.storage_file.exists():
            try:
                with self.storage_file.open("r", encoding="utf-8") as f:
                    self._oauth_connections = json.load(f)
                logger.info(
                    f"Loaded Composio OAuth connections from {self.storage_file}"
                )
            except Exception as e:
                logger.warning(f"Error loading Composio OAuth file: {e}")
        else:
            logger.info("No existing Composio OAuth file found.")

    # [ADDED] Save connections to disk
    def _save_persistence(self):
        try:
            self.storage_file.parent.mkdir(exist_ok=True)
            with self.storage_file.open("w", encoding="utf-8") as f:
                json.dump(self._oauth_connections, f, indent=2)
            logger.info("Saved Composio OAuth connections to disk.")
        except Exception as e:
            logger.error(f"Failed to save Composio OAuth connections: {e}")

    def _initialize_toolset(self):
        try:
            api_key = os.environ.get("COMPOSIO_API_KEY")
            if not api_key:
                logger.error("No COMPOSIO_API_KEY in environment")
                return
            self._toolset = ComposioToolSet(api_key=api_key, entity_id=self._entity_id)
            logger.info("Created ComposioToolSet instance")

            # Load the list of apps
            tools = self._toolset.get_tools(actions=["COMPOSIO_LIST_APPS"])
            result = self._toolset.execute_action(
                action="COMPOSIO_LIST_APPS", params={}, entity_id=self._entity_id
            )
            success_value = result.get("success") or result.get("successfull")
            if success_value:
                apps_data = result.get("data", {})
                apps_list = apps_data.get("apps", [])
                for app_info in apps_list:
                    key = app_info.get("key", "").upper()
                    if key:
                        self._available_apps[key] = app_info
                logger.info(
                    f"Fetched {len(self._available_apps)} apps from Composio meta-app"
                )
            else:
                logger.warning("COMPOSIO_LIST_APPS action failed.")
        except Exception as e:
            logger.error(f"Error init Composio: {e}", exc_info=True)
            self._available_apps = {}

    def mark_app_connected(self, app_name: str, connection_id: str):
        """Utility to mark an app as connected in our local _oauth_connections dict."""
        upper_app = app_name.upper()
        self._oauth_connections[upper_app] = {
            "connected": True,
            "connection_id": connection_id,
        }
        logger.info(
            f"mark_app_connected: Marked {upper_app} as connected with connection_id={connection_id}"
        )

        # [ADDED] Persist updated connections to disk
        self._save_persistence()

    async def initiate_oauth_flow(
        self, app_name: str, redirect_url: str
    ) -> Dict[str, Any]:
        """Begin an OAuth connection for a given app."""
        if not self._toolset:
            return {"success": False, "error": "Toolset not initialized"}

        try:
            upper_app = app_name.upper()
            app_info = self._available_apps.get(upper_app)
            if not app_info:
                return {"success": False, "error": f"Unknown app: {app_name}"}

            # Check if OAuth is supported
            auth_schemes = self._toolset.get_auth_schemes(app=app_info["key"])
            auth_modes = [scheme.auth_mode for scheme in auth_schemes]
            if "OAUTH2" not in auth_modes and "OAUTH1" not in auth_modes:
                return {
                    "success": False,
                    "error": "OAuth is not supported for this app",
                }

            logger.info(f"Initiating OAuth flow for {app_name}")
            connection_req = self._toolset.initiate_connection(
                redirect_url=redirect_url,
                entity_id=self._entity_id,
                app=app_info["key"],
                auth_scheme=auth_modes[0],
            )

            conn_id = getattr(connection_req, "connectionId", None)
            if not conn_id:
                conn_id = getattr(connection_req, "connectedAccountId", None)
            if not conn_id:
                return {"success": False, "error": "Failed to get connection ID"}

            return {
                "success": True,
                "redirect_url": connection_req.redirectUrl,
                "connection_id": conn_id,
            }
        except Exception as e:
            logger.error(
                f"initiate_oauth_flow error for {app_name}: {e}", exc_info=True
            )
            return {"success": False, "error": str(e)}

    async def handle_oauth_callback(
        self, connection_id: str, code: str
    ) -> Dict[str, Any]:
        """
        Finalize the OAuth flow for a given connection_id using the code from the provider.
        Then store 'connected' in _oauth_connections so our front-end can see that it's connected.
        """
        if not self._toolset:
            return {"success": False, "error": "Toolset not initialized"}

        try:
            result = self._toolset.complete_connection(
                connection_id=connection_id, code=code
            )
            if result.success:
                # Mark as connected
                app_key = result.app.upper() if result.app else "UNKNOWN"
                self.mark_app_connected(app_key, connection_id)
                logger.info(f"handle_oauth_callback: Marked {app_key} as connected.")
            else:
                logger.warning(f"handle_oauth_callback: success=False for {result.app}")

            return {
                "success": result.success,
                "app": result.app,
                "message": (
                    "Connection successful" if result.success else "Connection failed"
                ),
            }
        except Exception as e:
            logger.error(f"Error in handle_oauth_callback: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def mark_app_connected_without_code(self, app_name: str, connected_account_id: str):
        """
        If Composio doesn't require .complete_connection for some flows
        but returns connectedAccountId in the callback,
        we can directly mark the app as connected.
        """
        self.mark_app_connected(app_name, connected_account_id)

    async def list_available_integrations(self) -> List[Dict[str, Any]]:
        """
        Return a list of all apps from _available_apps,
        with "connected" = True if we've tracked them in _oauth_connections.
        """
        results = []
        for key, info in self._available_apps.items():
            upper_key = key.upper()
            is_connected = False
            if upper_key in self._oauth_connections and self._oauth_connections[
                upper_key
            ].get("connected"):
                is_connected = True

            results.append(
                {
                    "name": upper_key,  # e.g. "TWITTER"
                    "display_name": info.get("name", upper_key),
                    "connected": is_connected,
                    "oauth_supported": True,
                }
            )
        return results

    async def list_actions_for_app(self, app_name: str) -> Dict[str, Any]:
        """
        Returns a structure with all possible Composio actions for the given app_name,
        using a direct GET call to Composio's /api/v2/actions/list/all endpoint.

        Example return structure:
        {
            "success": True,
            "actions": [
                "TWITTER_TWEET_CREATE",
                "TWITTER_DM_SEND",
                ...
            ]
        }
        """
        upper_app = app_name.upper()

        # Check if the app is recognized in our local cache
        if upper_app not in self._available_apps:
            return {
                "success": False,
                "error": f"App '{app_name}' not recognized in _available_apps",
            }
        # Check if the app is connected
        if not self._oauth_connections.get(upper_app, {}).get("connected"):
            return {"success": False, "error": f"App '{app_name}' is not connected yet"}

        api_key = os.environ.get("COMPOSIO_API_KEY")
        if not api_key:
            return {"success": False, "error": "No COMPOSIO_API_KEY set in environment"}

        base_url = "https://backend.composio.dev/api/v2/actions/list/all"
        headers = {"x-api-key": api_key}
        params = {"apps": app_name.lower()}  # Composio expects lowercased

        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data_json = resp.json()
                items = data_json.get("items", [])
                actions = []
                for item in items:
                    action_key = item.get("actionKey")
                    if action_key:
                        actions.append(action_key)
                    else:
                        display_name = item.get("displayName")
                        if display_name:
                            actions.append(display_name)
                return {"success": True, "actions": actions}
            else:
                logger.error(
                    f"Composio API returned {resp.status_code} for app {app_name}"
                )
                return {
                    "success": False,
                    "error": f"Composio returned status {resp.status_code}",
                }
        except Exception as ex:
            logger.error(
                f"Error retrieving actions for {app_name} from Composio: {ex}",
                exc_info=True,
            )
            return {"success": False, "error": str(ex)}

    async def get_auth_schemes(self, app_name: str) -> Dict[str, Any]:
        """Get available authentication schemes for an app."""
        if not self._toolset:
            return {"success": False, "error": "Toolset not initialized"}

        try:
            upper_app = app_name.upper()
            app_info = self._available_apps.get(upper_app)
            if not app_info:
                return {"success": False, "error": f"Unknown app: {app_name}"}

            auth_schemes = self._toolset.get_auth_schemes(app=app_info["key"])
            auth_modes = [scheme.auth_mode for scheme in auth_schemes]

            # Get API key details if API_KEY auth is available
            api_key_details = None
            if "API_KEY" in auth_modes:
                auth_scheme = self._toolset.get_auth_scheme_for_app(
                    app=app_info["key"], auth_scheme="API_KEY"
                )
                # Get all fields for API_KEY auth
                api_key_details = {
                    "fields": [
                        {
                            "name": field.name,
                            "display_name": field.display_name,
                            "description": field.description,
                            "required": field.required,
                        }
                        for field in auth_scheme.fields
                    ]
                }

            return {
                "success": True,
                "auth_modes": auth_modes,
                "api_key_details": api_key_details,
            }
        except Exception as e:
            logger.error(
                f"Error getting auth schemes for {app_name}: {e}", exc_info=True
            )
            return {"success": False, "error": str(e)}


# Global single instance
composio_manager = ComposioManager()
