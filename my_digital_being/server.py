"""
Digital Being Server implementation.
Implements:
 - /oauth_callback endpoint to finalize OAuth after user is redirected back
 - WebSocket commands for front-end
 - Pause/Resume logic
 - Checking is_configured for front-end
 - [ADDED] Returning 'enabled' status for each loaded activity
"""

import asyncio
import json
import logging
import http
import mimetypes
from pathlib import Path
from typing import Dict, Any, Set, Union, Tuple
from datetime import datetime

import websockets
from websockets.server import serve
from websockets.legacy.server import WebSocketServerProtocol

# Initialize the logger with logging.INFO before importing other modules
# to make sure INFO level logs are printed (Otherwise it gets set to WARN)
logging.basicConfig(level=logging.INFO)

# Import api_manager at top-level (not again inside any function)
from framework.api_management import api_manager
from framework.main import DigitalBeing
from framework.skill_config import DynamicComposioSkills

logger = logging.getLogger(__name__)


class DigitalBeingServer:
    """Server for the Digital Being application."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.being = DigitalBeing()
        self.being_state: Dict[str, Any] = {}
        self.static_path = Path(__file__).parent / "static"

        # Additional flags for running/paused
        self.running = False
        self.paused = False

    async def initialize(self):
        """Initialize the digital being and start periodic updates."""
        logger.info("Initializing Digital Being...")
        self.being.initialize()  # load config, etc.

        self.running = True  # default "running"
        asyncio.create_task(self._periodic_state_update())
        asyncio.create_task(self._run_being_loop())

    async def _run_being_loop(self):
        """Main loop that calls the being's activities if running & not paused."""
        while True:
            try:
                if not self.running:
                    await asyncio.sleep(2)
                    continue

                if self.paused:
                    await asyncio.sleep(2)
                    continue

                if not self.being.is_configured():
                    # If not configured, do nothing in the main loop
                    await asyncio.sleep(2)
                    continue

                # Single-step approach for selecting an activity
                current_activity = self.being.activity_selector.select_next_activity()
                if current_activity:
                    logger.info(
                        f"Executing activity: {current_activity.__class__.__name__}"
                    )
                    result = await self.being.execute_activity(current_activity)
                    if result and result.success:
                        self.being_state["last_activity"] = {
                            "name": current_activity.__class__.__name__,
                            "timestamp": datetime.now().isoformat(),
                            "success": True,
                        }
                    else:
                        self.being_state["last_activity"] = {
                            "name": current_activity.__class__.__name__,
                            "timestamp": datetime.now().isoformat(),
                            "success": False,
                            "error": (result.error if result else "Unknown error"),
                        }
                    await self.broadcast_state()

                self.being.state.update()
                self.being.memory.persist()
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in being loop: {e}")
                await asyncio.sleep(10)

    async def _periodic_state_update(self):
        """Periodically update and broadcast the being's state every second."""
        while True:
            try:
                current_state = self.being.state.get_current_state()
                # Provide 'configured' and 'paused' status
                current_state["configured"] = self.being.is_configured()
                current_state["paused"] = self.paused

                if current_state != self.being_state:
                    self.being_state = current_state
                    await self.broadcast_state()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in periodic state update: {e}")
                await asyncio.sleep(5)

    async def register(self, websocket: WebSocketServerProtocol):
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

        # Send the current state right away
        await websocket.send(
            json.dumps({"type": "state_update", "data": self.being_state})
        )

    async def unregister(self, websocket: WebSocketServerProtocol):
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def serve_static_file(
        self, path: str, request_headers: Dict
    ) -> Union[Tuple[http.HTTPStatus, list, bytes], None]:
        try:
            if path == "/ws":
                return None

            if path.startswith("/oauth_callback"):
                return await self.handle_oauth_http_callback(path)

            if not isinstance(path, str):
                return None

            request_path = "/" + path.lstrip("/")
            if request_path == "/":
                request_path = "/index.html"

            if request_path == "/ws":
                if (
                    request_headers.get("Upgrade", "").lower() == "websocket"
                    and request_headers.get("Connection", "").lower() == "upgrade"
                ):
                    logger.info("Valid WebSocket upgrade request")
                    return None
                logger.warning("Invalid WebSocket request")
                return (
                    http.HTTPStatus.BAD_REQUEST,
                    [("Content-Type", "text/plain")],
                    b"Invalid WebSocket request",
                )

            file_path = self.static_path / request_path.lstrip("/")
            if not file_path.exists() or not file_path.is_file():
                logger.warning(f"File not found: {file_path}")
                return (
                    http.HTTPStatus.NOT_FOUND,
                    [("Content-Type", "text/plain")],
                    b"404 Not Found",
                )

            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

            content = file_path.read_bytes()
            return (
                http.HTTPStatus.OK,
                [
                    ("Content-Type", content_type),
                    ("Cache-Control", "public, max-age=3600"),
                ],
                content,
            )

        except Exception as e:
            logger.error(f"Error serving {path}: {e}")
            return (
                http.HTTPStatus.INTERNAL_SERVER_ERROR,
                [("Content-Type", "text/plain")],
                b"Internal Server Error",
            )

    async def handle_oauth_http_callback(self, path: str):
        """
        Handle GET /oauth_callback?status=success&connectedAccountId=...&appName=...
        Then finalize or store connection info, auto-fetch & register app actions,
        and finally redirect to "/".
        """
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(path)
        query = parse_qs(parsed.query)

        status = query.get("status", [""])[0]
        connected_account_id = query.get("connectedAccountId", [None])[0]
        app_name = query.get("appName", [""])[0]
        code = query.get("code", [None])[0]

        if not connected_account_id:
            logger.error("Missing connectedAccountId param in /oauth_callback")
            body = b"Missing connectedAccountId param"
            return (
                http.HTTPStatus.BAD_REQUEST,
                [("Content-Type", "text/plain")],
                body,
            )

        logger.info(
            f"OAuth callback success for app={app_name}, connectedAccountId={connected_account_id}, status={status}"
        )

        try:
            if code:
                finalize_result = (
                    await api_manager.composio_manager.handle_oauth_callback(
                        connected_account_id, code
                    )
                )
                logger.info(f"handle_oauth_callback returned: {finalize_result}")
            else:
                if app_name:
                    api_manager.composio_manager.mark_app_connected_without_code(
                        app_name, connected_account_id
                    )

            if app_name:
                logger.info(
                    f"Auto-fetching actions for newly connected app: {app_name}"
                )
                actions_result = await api_manager.list_actions_for_app(app_name)
                if actions_result.get("success"):
                    actions = actions_result.get("actions", [])
                    if actions:
                        logger.info(
                            f"Discovered {len(actions)} actions for {app_name}, registering now..."
                        )
                        DynamicComposioSkills.register_composio_actions(
                            app_name, actions
                        )
                    else:
                        logger.warning(f"No actions found for {app_name}.")
                else:
                    logger.warning(
                        f"Failed to fetch actions for {app_name}: {actions_result.get('error')}"
                    )

        except Exception as e:
            logger.error(
                f"Error finalizing/fetching actions for {app_name}: {e}", exc_info=True
            )

        redirect_body = b'<html><head><meta http-equiv="refresh" content="0;URL=\'/\'" /></head><body>Redirecting...</body></html>'
        return (
            http.HTTPStatus.OK,
            [("Content-Type", "text/html")],
            redirect_body,
        )

    async def handle_websocket(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket connections at /ws."""
        try:
            if path != "/ws":
                logger.warning(f"Invalid WebSocket path: {path}")
                await websocket.close(code=1008, reason="Invalid path")
                return

            await self.register(websocket)
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.process_message(websocket, data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON: {message}")
                    except Exception as e:
                        logger.error(f"Error processing WS message: {e}")
            except websockets.ConnectionClosed:
                logger.info("WebSocket closed normally")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
        finally:
            await self.unregister(websocket)

    async def process_message(
        self, websocket: WebSocketServerProtocol, data: Dict[str, Any]
    ):
        try:
            message_type = data.get("type")
            if not message_type:
                logger.warning("No message type in WS data!")
                return

            if message_type == "get_state":
                await websocket.send(
                    json.dumps({"type": "state_update", "data": self.being_state})
                )
            elif message_type == "command":
                command = data.get("command")
                if command:
                    resp = await self.handle_command(command, data.get("params", {}))
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "command_response",
                                "command": command,
                                "response": resp,
                            }
                        )
                    )
        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))

    async def handle_command(
        self, command: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.debug(f"handle_command: {command}, params={params}")
        try:
            if command == "pause":
                self.paused = True
                return {"success": True, "message": "Digital Being is paused."}
            elif command == "resume":
                self.paused = False
                return {"success": True, "message": "Digital Being resumed."}
            elif command == "stop_loop":
                self.running = False
                return {"success": True, "message": "Core loop stopped."}
            elif command == "start_loop":
                self.running = True
                return {"success": True, "message": "Core loop started."}

            elif command == "initiate_oauth":
                app_name = params.get("app_name")
                base_url = params.get("base_url", "http://localhost:8000")
                if not app_name:
                    return {"success": False, "error": "Missing app_name"}
                redirect_url = f"{base_url}/oauth_callback"
                try:
                    result = await api_manager.composio_manager.initiate_oauth_flow(
                        app_name, redirect_url
                    )
                    return result
                except Exception as e:
                    logger.error(f"init_oauth error: {e}")
                    return {"success": False, "error": str(e)}

            elif command == "get_composio_integrations":
                try:
                    integrations = (
                        await api_manager.composio_manager.list_available_integrations()
                    )
                    return {"success": True, "composio_integrations": integrations}
                except Exception as e:
                    logger.error(f"Error get_composio_integrations: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "composio_integrations": [],
                    }

            elif command == "get_api_key_status":
                skills_status = await api_manager.get_skill_status()
                return {"success": True, "skills": skills_status}

            elif command == "configure_api_key":
                skill_name = params.get("skill_name")
                key_name = params.get("key_name")
                api_key_value = params.get("api_key")
                if not all([skill_name, key_name, api_key_value]):
                    return {"success": False, "message": "Missing required params"}
                try:
                    result = await api_manager.set_api_key(
                        skill_name, key_name, api_key_value
                    )
                    return result
                except Exception as e:
                    return {"success": False, "message": str(e)}

            elif command == "get_system_status":
                memory_stats = {
                    "short_term_count": len(self.being.memory.short_term_memory),
                    "long_term_count": sum(
                        len(x) for x in self.being.memory.long_term_memory.values()
                    ),
                    "total_activities": self.being.memory.get_activity_count(),
                }
                current_state = self.being.state.get_current_state()
                is_config = self.being.is_configured()

                return {
                    "success": True,
                    "memory": memory_stats,
                    "state": current_state,
                    "is_configured": is_config,
                    "config": self.being.configs,
                }

            elif command == "get_activities":
                # Return loaded activities with 'enabled' status from activity_constraints
                acts = self.being.activity_loader.get_all_activities()
                info = {}

                activities_config = {}
                if (
                    "activity_constraints" in self.being.configs
                    and "activities_config"
                    in self.being.configs["activity_constraints"]
                ):
                    activities_config = self.being.configs["activity_constraints"][
                        "activities_config"
                    ]

                for module_name, cls in acts.items():
                    class_name = cls.__name__
                    is_enabled = True
                    if class_name in activities_config:
                        is_enabled = bool(
                            activities_config[class_name].get("enabled", True)
                        )

                    info[module_name] = {
                        "name": class_name,
                        "energy_cost": cls.energy_cost,
                        "cooldown": cls.cooldown,
                        "required_skills": cls.required_skills,
                        "last_execution": (
                            cls.last_execution.isoformat()
                            if cls.last_execution
                            else None
                        ),
                        "enabled": is_enabled,
                    }
                return {"success": True, "activities": info}

            elif command == "get_config":
                return {"success": True, "config": self.being.configs}

            elif command == "update_config":
                section = params.get("section")
                key = params.get("key")
                value = params.get("value")

                if not section or not key:
                    return {
                        "success": False,
                        "message": "Both 'section' and 'key' are required.",
                    }

                # Map sections to config files
                section_to_file = {
                    "character_config": "character_config.json",
                    "skills_config": "skills_config.json",
                    "activity_constraints": "activity_constraints.json",
                }

                config_file_name = section_to_file.get(section)
                if not config_file_name:
                    return {
                        "success": False,
                        "message": f"Unknown configuration section: {section}",
                    }

                config_path = Path(self.being.config_path) / config_file_name

                try:
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            current_config = json.load(f)
                    else:
                        current_config = {}
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse {config_file_name}: {je}")
                    return {
                        "success": False,
                        "message": f"Invalid JSON format in {config_file_name}.",
                    }
                except Exception as e:
                    logger.error(f"Error loading {config_file_name}: {e}")
                    return {
                        "success": False,
                        "message": f"Error loading {config_file_name}.",
                    }

                # Update the config
                current_config[key] = value

                # Write back
                try:
                    with open(config_path, "w") as f:
                        json.dump(current_config, f, indent=2)
                except Exception as e:
                    logger.error(f"Failed to write to {config_file_name}: {e}")
                    return {
                        "success": False,
                        "message": f"Failed to write to {config_file_name}.",
                    }

                # Update in-memory
                self.being.configs[section][key] = value
                logger.info(f"Updated config: [{section}] {key} = {value}")

                return {
                    "success": True,
                    "message": f"Configuration '{key}' updated successfully.",
                }

            elif command == "get_activity_history":
                limit = params.get("limit", 10)
                offset = params.get("offset", 0)
                recents = self.being.memory.get_recent_activities(limit=limit, offset=offset)
                total = self.being.memory.get_activity_count()
                return {
                    "success": True,
                    "activities": recents,
                    "has_more": total > (offset + limit),
                    "total": total,
                }

            elif command == "get_composio_app_actions":
                app_name = params.get("app_name")
                result = await api_manager.list_actions_for_app(app_name)
                if result.get("success"):
                    DynamicComposioSkills.register_composio_actions(
                        app_name, result.get("actions", [])
                    )
                return result

            elif command == "get_all_skills":
                config_skills = self.being.configs.get("skills_config", {})
                manual_skills_list = []
                for skill_name, skill_info in config_skills.items():
                    if not isinstance(skill_info, dict):
                        logger.debug(
                            f"Skipping non-dict skill config: {skill_name} => {skill_info}"
                        )
                        continue
                    manual_skills_list.append(
                        {
                            "skill_name": skill_name,
                            "enabled": bool(skill_info.get("enabled", False)),
                            "metadata": skill_info,
                        }
                    )

                dynamic_skills = DynamicComposioSkills.get_all_dynamic_skills()
                all_skills = manual_skills_list + dynamic_skills
                return {"success": True, "skills": all_skills}

            elif command == "get_activity_code":
                from framework.activity_loader import read_activity_code
                activity_name = params.get("activity_name")
                code_str = read_activity_code(activity_name)
                if code_str is None:
                    return {
                        "success": False,
                        "message": f"Could not read code for {activity_name}",
                    }
                return {"success": True, "code": code_str}

            elif command == "save_activity_code":
                from framework.activity_loader import write_activity_code
                activity_name = params.get("activity_name")
                new_code = params.get("new_code")
                ok = write_activity_code(activity_name, new_code)
                if not ok:
                    return {"success": False, "message": "Failed to save code"}
                self.being.activity_loader.reload_activities()
                return {"success": True, "message": "Code updated and reloaded"}

            elif command == "save_onboarding_data":
                """
                Expects 'character', 'skills', and 'constraints' from front-end.
                The 'skills' object may have e.g.:
                  {
                    "lite_llm": {
                      "enabled": true,
                      "model_name": "openai/gpt-4o",
                      "required_api_keys": ["LITELLM"],
                      "provided_api_key": "sk-1234abcd..."
                    },
                    "default_llm_skill": "lite_llm"
                  }
                """
                try:
                    char_data = params.get("character", {})
                    skills_data = params.get("skills", {})
                    constraints_data = params.get("constraints", {})

                    char_path = Path(self.being.config_path) / "character_config.json"
                    skill_path = Path(self.being.config_path) / "skills_config.json"
                    actc_path = Path(self.being.config_path) / "activity_constraints.json"

                    existing_char = {}
                    existing_skills = {}
                    existing_actc = {}

                    # Load existing JSON
                    if char_path.exists():
                        existing_char = json.loads(char_path.read_text(encoding="utf-8"))
                    if skill_path.exists():
                        existing_skills = json.loads(skill_path.read_text(encoding="utf-8"))
                    if actc_path.exists():
                        existing_actc = json.loads(actc_path.read_text(encoding="utf-8"))

                    # Merge the new data
                    existing_char.update(char_data)
                    existing_skills.update(skills_data)
                    for k, v in constraints_data.items():
                        existing_actc[k] = v

                    # Possibly set "setup_complete"
                    existing_char["setup_complete"] = True

                    # If user provided an API key for any skill, store it with secret manager
                    for skill_name, skill_info in skills_data.items():
                        if not isinstance(skill_info, dict):
                            continue
                        maybe_key = skill_info.get("provided_api_key")
                        if maybe_key:
                            required_keys = skill_info.get("required_api_keys", [])
                            if required_keys:
                                main_key = required_keys[0]
                                await api_manager.set_api_key(skill_name, main_key, maybe_key)

                            # Remove 'provided_api_key' from final JSON if you prefer
                            if "provided_api_key" in existing_skills[skill_name]:
                                del existing_skills[skill_name]["provided_api_key"]

                    # Save the updated JSON
                    char_path.write_text(json.dumps(existing_char, indent=2), encoding="utf-8")
                    skill_path.write_text(json.dumps(existing_skills, indent=2), encoding="utf-8")
                    actc_path.write_text(json.dumps(existing_actc, indent=2), encoding="utf-8")

                    # Reload in memory
                    self.being.configs["character_config"] = existing_char
                    self.being.configs["skills_config"] = existing_skills
                    self.being.configs["activity_constraints"] = existing_actc

                    return {"success": True, "message": "Onboarding data saved."}

                except Exception as e:
                    logger.error(f"Error saving onboarding data: {e}", exc_info=True)
                    return {"success": False, "message": str(e)}

            elif command == "get_auth_schemes":
                app_name = params.get("app_name")
                if not app_name:
                    return {"success": False, "error": "Missing app_name"}
                try:
                    result = await api_manager.get_auth_schemes(app_name)
                    return result
                except Exception as e:
                    logger.error(f"get_auth_schemes error: {e}")
                    return {"success": False, "error": str(e)}

            elif command == "initiate_api_key_connection":
                app_name = params.get("app_name")
                connection_params = params.get("connection_params")
                if not app_name or not connection_params:
                    return {"success": False, "error": "Missing app_name or connection_params"}
                try:
                    result = await api_manager.initiate_api_key_connection(app_name, connection_params)
                    return result
                except Exception as e:
                    logger.error(f"initiate_api_key_connection error: {e}")
                    return {"success": False, "error": str(e)}

            elif command == "initiate_oauth_with_params":
                app_name = params.get("app_name")
                base_url = params.get("base_url", "http://localhost:8000")
                connection_params = params.get("connection_params")
                if not app_name or not connection_params:
                    return {"success": False, "error": "Missing app_name or connection_params"}
                redirect_url = f"{base_url}/oauth_callback"
                try:
                    result = await api_manager.composio_manager.initiate_oauth_with_params(
                        app_name, redirect_url, connection_params
                    )
                    return result
                except Exception as e:
                    logger.error(f"initiate_oauth_with_params error: {e}")
                    return {"success": False, "error": str(e)}

        except Exception as e:
            logger.error(f"handle_command {command} error: {e}")
            return {"success": False, "message": str(e)}

        return {"success": False, "message": "Unknown command"}

    async def broadcast_state(self):
        """Broadcast the current being_state to all connected WebSocket clients."""
        if not self.clients:
            return
        message = json.dumps({"type": "state_update", "data": self.being_state})
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.ConnectionClosed:
                logger.info("Client disconnected during broadcast")
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected_clients.add(client)

        for dc in disconnected_clients:
            await self.unregister(dc)

    async def start_server(self):
        """Start the server using websockets.serve()."""
        try:
            await self.initialize()
            async with serve(
                self.handle_websocket,
                self.host,
                self.port,
                process_request=self.serve_static_file,
            ):
                logger.info(f"Server started on ws://{self.host}:{self.port}")
                await asyncio.Future()  # run forever
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise


if __name__ == "__main__":
    server = DigitalBeingServer()
    asyncio.run(server.start_server())
