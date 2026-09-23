import os
import json
import httpx
from typing import Optional

BROKER_TOOLS = [
    {
        "name": "manage_solace_queue",
        "description": "Get, create, update, delete, or duplicate a queue on the Solace event broker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "create", "update", "delete", "duplicate"],
                    "description": "The action to perform on the queue."
                },
                "queue_name": {
                    "type": "string",
                    "description": "The exact name of the queue."
                },
                "new_queue_name": {
                    "type": "string",
                    "description": "For duplicate action: The new queue name."
                },
                "max_ttl": {
                    "type": "integer",
                    "description": "For create, update, duplicate: The maximum TTL in seconds (0 for infinite)."
                },
                "max_msg_spool_usage": {
                    "type": "integer",
                    "description": "For create, update: The maximum spool usage in MB."
                }
            },
            "required": ["action", "queue_name"]
        }
    },
    {
        "name": "get_queue_stats",
        "description": "Read-only tool to fetch live telemetry for a queue, including message counts, spool usage, and currently bound consumers/clients.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "queue_name": {
                    "type": "string",
                    "description": "The exact name of the queue."
                }
            },
            "required": ["queue_name"]
        }
    },
    {
        "name": "list_queues",
        "description": "Read-only tool to list all queues on the broker along with their basic telemetry (spool usage, active consumers, etc). Use this when asked to find queues matching a condition.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_queue_subscriptions",
        "description": "Read-only tool to list all topic subscriptions configured on a specific queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "queue_name": {
                    "type": "string",
                    "description": "The exact name of the queue."
                }
            },
            "required": ["queue_name"]
        }
    },
    {
        "name": "manage_queue_subscription",
        "description": "List, add, or remove topic subscriptions on a specific queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove"],
                    "description": "The action to perform."
                },
                "queue_name": {
                    "type": "string",
                    "description": "The exact name of the queue."
                },
                "topic": {
                    "type": "string",
                    "description": "The exact topic string. Required for add/remove."
                }
            },
            "required": ["action", "queue_name"]
        }
    },
    {
        "name": "get_client_username",
        "description": "Read-only tool to fetch the configuration of a client username, which includes its assigned ACL profile and Client profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_username": {
                    "type": "string",
                    "description": "The exact name of the client username to look up."
                }
            },
            "required": ["client_username"]
        }
    }
]

async def _semp_request(method: str, path: str, body: dict = None) -> dict:
    base_url = os.getenv("SOLACE_SEMPV2_BASE_URL", "").rstrip("/")
    username = os.getenv("SOLACE_SEMPV2_USERNAME", "")
    password = os.getenv("SOLACE_SEMPV2_PASSWORD", "")
    
    if not base_url or not username:
        return {"error": "Broker credentials (SOLACE_SEMPV2_BASE_URL, SOLACE_SEMPV2_USERNAME) not configured in environment."}
        
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                auth=(username, password),
                json=body,
                timeout=10.0
            )
            
            if response.status_code >= 400:
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "detail": response.text[:500]
                }
            if response.status_code == 204:
                return {"success": True, "message": "Operation completed (no content)"}
                
            return response.json()
        except Exception as e:
            return {"error": True, "detail": str(e)}


async def _manage_queue(action: str, queue_name: str, args: dict) -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    
    if action == "get":
        config = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}")
        monitor = await _semp_request("GET", f"/SEMP/v2/monitor/msgVpns/{vpn}/queues/{queue_name}")
        return {"config": config, "monitor": monitor}
        
    elif action == "delete":
        return await _semp_request("DELETE", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}")
        
    elif action == "create":
        body = {
            "queueName": queue_name,
            "msgVpnName": vpn,
            "accessType": "non-exclusive",
            "permission": "consume",
            "ingressEnabled": True,
            "egressEnabled": True
        }
        if "max_ttl" in args:
            body["maxTtl"] = args["max_ttl"]
        if "max_msg_spool_usage" in args:
            body["maxMsgSpoolUsage"] = args["max_msg_spool_usage"]
            
        return await _semp_request("POST", f"/SEMP/v2/config/msgVpns/{vpn}/queues", body)
        
    elif action == "update":
        body = {}
        if "max_ttl" in args:
            body["maxTtl"] = args["max_ttl"]
        if "max_msg_spool_usage" in args:
            body["maxMsgSpoolUsage"] = args["max_msg_spool_usage"]
            
        if not body:
            return {"error": "No update parameters provided."}
            
        return await _semp_request("PATCH", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}", body)
        
    elif action == "duplicate":
        new_queue_name = args.get("new_queue_name")
        if not new_queue_name:
            return {"error": "new_queue_name is required for duplicate action"}
            
        source = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}")
        if "error" in source:
            return source
            
        source_data = source.get("data", {})
        if not source_data:
            return {"error": f"Source queue {queue_name} not found"}
            
        new_body = {
            "queueName": new_queue_name,
            "msgVpnName": vpn,
            "accessType": source_data.get("accessType", "non-exclusive"),
            "maxMsgSpoolUsage": args.get("max_msg_spool_usage", source_data.get("maxMsgSpoolUsage", 5000)),
            "permission": source_data.get("permission", "consume"),
            "ingressEnabled": source_data.get("ingressEnabled", True),
            "egressEnabled": source_data.get("egressEnabled", True),
            "maxTtl": args.get("max_ttl", source_data.get("maxTtl", 0)),
            "maxBindCount": source_data.get("maxBindCount", 1000),
            "maxDeliveredUnackedMsgsPerFlow": source_data.get("maxDeliveredUnackedMsgsPerFlow", 10000),
            "maxMsgSize": source_data.get("maxMsgSize", 10000000),
            "respectTtlEnabled": source_data.get("respectTtlEnabled", False),
        }
        
        result = await _semp_request("POST", f"/SEMP/v2/config/msgVpns/{vpn}/queues", new_body)
        
        # Copy subscriptions
        subs = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}/subscriptions")
        copied_subs = []
        if "data" in subs:
            for sub in subs["data"]:
                topic = sub.get("subscriptionTopic", "")
                if topic:
                    sub_result = await _semp_request(
                        "POST", 
                        f"/SEMP/v2/config/msgVpns/{vpn}/queues/{new_queue_name}/subscriptions",
                        {"subscriptionTopic": topic, "msgVpnName": vpn, "queueName": new_queue_name}
                    )
                    copied_subs.append({"topic": topic, "result": "ok" if "error" not in sub_result else "failed"})
                    
        return {"queue_created": result, "subscriptions_copied": copied_subs}
        
    return {"error": f"Unknown action: {action}"}


async def _manage_subscription(action: str, queue_name: str, args: dict) -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    topic = args.get("topic")
    
    if action == "list":
        return await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}/subscriptions")
        
    if action in ["add", "remove"] and not topic:
        return {"error": "topic is required for add/remove actions."}
        
    if action == "add":
        body = {
            "subscriptionTopic": topic,
            "msgVpnName": vpn,
            "queueName": queue_name
        }
        return await _semp_request("POST", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}/subscriptions", body)
        
    elif action == "remove":
        import urllib.parse
        encoded_topic = urllib.parse.quote(topic, safe="")
        return await _semp_request("DELETE", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}/subscriptions/{encoded_topic}")
        
    return {"error": f"Unknown action: {action}"}


async def _get_queue_stats(queue_name: str) -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    
    config = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}")
    monitor = await _semp_request("GET", f"/SEMP/v2/monitor/msgVpns/{vpn}/queues/{queue_name}")
    tx_flows = await _semp_request("GET", f"/SEMP/v2/monitor/msgVpns/{vpn}/queues/{queue_name}/txFlows")
    
    clients = []
    if "data" in tx_flows:
        for flow in tx_flows["data"]:
            if "clientName" in flow:
                clients.append(flow["clientName"])
                
    return {
        "config": config.get("data", {}),
        "monitor_stats": {
            "spooledMsgCount": monitor.get("data", {}).get("spooledMsgCount", 0),
            "msgSpoolUsage": monitor.get("data", {}).get("msgSpoolUsage", 0),
            "bindCount": monitor.get("data", {}).get("bindCount", 0)
        },
        "connected_client_names": clients
    }


async def _get_client_username(client_username: str) -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    
    # 1. Fetch Client Username config
    cu_config = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/clientUsernames/{client_username}")
    if "error" in cu_config:
        return cu_config
        
    cu_data = cu_config.get("data", {})
    acl_profile_name = cu_data.get("aclProfileName")
    
    # 2. Fetch the assigned ACL profile
    acl_config = {}
    if acl_profile_name:
        acl_res = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/aclProfiles/{acl_profile_name}")
        acl_config = acl_res.get("data", {})
        
    return {
        "client_username_config": cu_data,
        "acl_profile_config": acl_config
    }


async def _list_queues() -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    response = await _semp_request("GET", f"/SEMP/v2/monitor/msgVpns/{vpn}/queues?count=100")
    
    if "error" in response:
        return response
        
    queues = response.get("data", [])
    simplified = []
    for q in queues:
        simplified.append({
            "queue_name": q.get("queueName"),
            "active_consumers": q.get("bindCount", 0),
            "messages_spooled": q.get("spooledMsgCount", 0),
            "spool_usage_bytes": q.get("msgSpoolUsage", 0),
            "max_spool_usage_mb": q.get("maxMsgSpoolUsage", 0)
        })
        
    return {"queues": simplified}


async def _get_queue_subscriptions(queue_name: str) -> dict:
    vpn = os.getenv("SOLACE_SEMPV2_VPN", "default")
    res = await _semp_request("GET", f"/SEMP/v2/config/msgVpns/{vpn}/queues/{queue_name}/subscriptions")
    if "error" in res:
        return res
        
    subs = []
    if "data" in res:
        for sub in res["data"]:
            if "subscriptionTopic" in sub:
                subs.append(sub["subscriptionTopic"])
                
    return {"topic_subscriptions": subs}


async def execute_broker_tool(tool_name: str, args: dict) -> str:
    if tool_name == "manage_solace_queue":
        res = await _manage_queue(args.get("action"), args.get("queue_name"), args)
    elif tool_name == "manage_queue_subscription":
        res = await _manage_subscription(args.get("action"), args.get("queue_name"), args)
    elif tool_name == "get_queue_stats":
        res = await _get_queue_stats(args.get("queue_name"))
    elif tool_name == "list_queues":
        res = await _list_queues()
    elif tool_name == "get_queue_subscriptions":
        res = await _get_queue_subscriptions(args.get("queue_name"))
    elif tool_name == "get_client_username":
        res = await _get_client_username(args.get("client_username"))
    else:
        res = {"error": f"Unknown broker tool: {tool_name}"}
        
    return json.dumps(res, indent=2)
