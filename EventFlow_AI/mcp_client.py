"""
EventFlow_AI/mcp_client.py
---------------------------
Manages the persistent async connection to the Solace MCP Server.
Implements the "Smart Router" architecture, exposing generalized
tools to the LLM and orchestrating the complex relational Solace
REST calls underneath.
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import config

# ── MCP Server Parameters ─────────────────────────────────────────────────
def _get_server_params() -> StdioServerParameters:
    env = {
        **os.environ,
        "SOLACE_API_TOKEN": config.SOLACE_API_TOKEN,
        "SOLACE_API_BASE_URL": config.SOLACE_API_BASE_URL,
    }
    
    # Use the local modified package
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mcp_path = os.path.join(base_dir, "Solace_MCP_Server", "solace-event-portal-designer-mcp")
    
    return StdioServerParameters(
        command="uvx",
        args=["-q", "--from", mcp_path, "solace-ep-designer-mcp"],
        env=env,
    )

# ── Context Manager ────────────────────────────────────────────────────────
@asynccontextmanager
async def managed_session():
    """Async context manager that yields an initialized MCP ClientSession."""
    async with stdio_client(_get_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


# ── Generalized Tool Schemas for LLM ───────────────────────────────────────
GENERALIZED_TOOLS = [
    {
        "name": "search_solace_entity",
        "description": "Lists all entities of a given type, or finds a specific entity if 'name' is provided.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["domain", "application", "event", "event_api", "event_api_product", "schema", "enum"],
                    "description": "The type of entity you want to list or search for."
                },
                "name": {
                    "type": "string",
                    "description": "Optional. The exact name of the entity to search for. If omitted, lists all entities of the specified type."
                },
                "domain_name": {
                    "type": "string",
                    "description": "Optional. The exact name of the domain to filter the search results by."
                },
                "entity_id": {
                    "type": "string",
                    "description": "Optional. The exact ID of the entity to search for. When provided, looks up the specific entity by ID."
                }
            },
            "required": ["entity_type"]
        }
    },
    {
        "name": "get_entity_relationships",
        "description": "Fetches the related objects (like applications inside a domain, or events produced/consumed by an application).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The ID of the parent entity."
                },
                "relationship_type": {
                    "type": "string",
                    "enum": ["applications", "produced_events", "consumed_events", "event_apis", "consuming_applications"],
                    "description": "The type of relationship you want to explore."
                }
            },
            "required": ["entity_id", "relationship_type"]
        }
    },
    {
        "name": "duplicate_solace_entity",
        "description": "Duplicates an existing entity, copying its configuration and relationships to a new entity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["application", "event", "event_api", "event_api_product"],
                    "description": "The type of entity you want to duplicate."
                },
                "source_entity_id": {
                    "type": "string",
                    "description": "The ID of the existing entity to duplicate."
                },
                "new_name": {
                    "type": "string",
                    "description": "The exact name for the new duplicate entity."
                }
            },
            "required": ["entity_type", "source_entity_id", "new_name"]
        }
    },
    {
        "name": "update_entity_relationship",
        "description": "Updates the relationships of a specific version of an entity (e.g., adding an event to an event API).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["application", "event_api", "event_api_product"],
                    "description": "The type of entity version you are updating."
                },
                "version_id": {
                    "type": "string",
                    "description": "The ID of the specific entity VERSION to update."
                },
                "action": {
                    "type": "string",
                    "enum": ["add", "remove"],
                    "description": "Whether to add or remove the relationship."
                },
                "target_type": {
                    "type": "string",
                    "enum": ["event", "event_api"],
                    "description": "The type of the target entity version being linked."
                },
                "target_version_id": {
                    "type": "string",
                    "description": "The ID of the target entity VERSION to link/unlink."
                }
            },
            "required": ["entity_type", "version_id", "action", "target_type", "target_version_id"]
        }
    },
    {
        "name": "get_entity_impact",
        "description": "Finds out what other entities rely on or reference a given entity version (reverse dependency lookup).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["event", "schema", "event_api"],
                    "description": "The type of entity you are analyzing."
                },
                "version_id": {
                    "type": "string",
                    "description": "The ID of the specific entity VERSION."
                }
            },
            "required": ["entity_type", "version_id"]
        }
    },
    {
        "name": "get_schema_content",
        "description": "Smart tool that retrieves the actual JSON or AVRO schema data fields. You can pass an Event ID, Event Version ID, Schema ID, or Schema Version ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The ID of the event or schema entity to fetch content for."
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "create_solace_entity",
        "description": "Creates a new Solace Domain, Application, or Event, along with its initial version (0.1.0).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["domain", "application", "event", "event_api", "event_api_product", "schema", "enum"],
                    "description": "The type of entity you want to create."
                },
                "name": {
                    "type": "string",
                    "description": "The exact name of the new entity."
                },
                "domain_name": {
                    "type": "string",
                    "description": "The exact name of the domain where this entity should reside. Required for applications and events."
                },
                "enum_values": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required when creating an enum. The list of string values for the enumeration."
                }
            },
            "required": ["entity_type", "name"]
        }
    },
    {
        "name": "create_solace_entity_version",
        "description": "Creates a new version for an existing Application, Event, Event API, or Event API Product.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["application", "event", "event_api", "event_api_product", "schema", "enum"],
                    "description": "The type of entity you are versioning."
                },
                "entity_id": {
                    "type": "string",
                    "description": "The ID of the parent entity."
                },
                "version": {
                    "type": "string",
                    "description": "The new version string (e.g. '1.0.0')."
                },
                "enum_values": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required when versioning an enum. The list of string values for the enumeration."
                }
            },
            "required": ["entity_type", "entity_id", "version"]
        }
    },
    {
        "name": "delete_solace_entity",
        "description": "Deletes a specific Solace Domain, Application, Event, Event API, or Event API Product.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["domain", "application", "event", "event_api", "event_api_product", "schema", "enum"],
                    "description": "The type of entity you are deleting."
                },
                "entity_id": {
                    "type": "string",
                    "description": "The ID of the entity to delete."
                }
            },
            "required": ["entity_type", "entity_id"]
        }
    },
    {
        "name": "delete_solace_entity_version",
        "description": "Deletes a specific version of a Solace Application, Event, Event API, or Event API Product.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["application", "event", "event_api", "event_api_product", "schema", "enum"],
                    "description": "The type of entity version you are deleting."
                },
                "version_id": {
                    "type": "string",
                    "description": "The unique ID of the version to delete."
                }
            },
            "required": ["entity_type", "version_id"]
        }
    }
]

# ── Smart Router Logic (Python Backend) ────────────────────────────────────

async def _call_mcp(session: ClientSession, tool_name: str, args: dict) -> list | dict:
    """Helper to execute an MCP tool and parse its JSON output."""
    try:
        result = await session.call_tool(tool_name, args)
        parts = [c.text for c in result.content if c.type == "text"]
        text = "".join(parts)
        if not text.strip():
            return []
        
        try:
            parsed = json.loads(text)
            return parsed.get("data", parsed)
        except json.JSONDecodeError:
            # If the server returned an error string instead of JSON
            return {"error": text}
    except Exception as e:
        print(f"[DEBUG] MCP Call failed: {tool_name} with {args} - {e}")
        return []


async def _search_entity(session: ClientSession, entity_type: str, name: str = None, domain_name: str = None, entity_id: str = None) -> dict:
    """Executes the search_solace_entity logic."""
    args = {}
    if entity_id:
        args["ids"] = [entity_id]
    if name:
        args["name"] = name
        
    if domain_name and entity_type != "domain":
        # Resolve the domain name to an applicationDomainId
        domain_res = await _call_mcp(session, "getApplicationDomains", {"name": domain_name})
        if not domain_res:
            return {"error": f"Domain '{domain_name}' not found."}
        args["applicationDomainId"] = domain_res[0]["id"]
    
    data = []
    if entity_type == "domain":
        data = await _call_mcp(session, "getApplicationDomains", args)
    elif entity_type == "application":
        data = await _call_mcp(session, "getApplications", args)
    elif entity_type == "event":
        data = await _call_mcp(session, "getEvents", args)
    elif entity_type == "event_api":
        data = await _call_mcp(session, "getEventApis", args)
    elif entity_type == "event_api_product":
        data = await _call_mcp(session, "getEventApiProducts", args)
    elif entity_type == "schema":
        data = await _call_mcp(session, "getSchemas", args)
    elif entity_type == "enum":
        if "name" in args: args["names"] = [args.pop("name")]
        data = await _call_mcp(session, "getEnums", args)
    else:
        return {"error": f"Unsupported entity_type: {entity_type}"}

    if entity_type == "domain" or not isinstance(data, list):
        return {"result": data}

    enriched_results = []
    for item in data:
        if isinstance(item, dict) and "id" in item:
            version_tool = f"get{entity_type.replace('_', ' ').title().replace(' ', '')}Versions"
            id_param = f"{entity_type.replace('_', ' ').title().replace(' ', '')[:1].lower() + entity_type.replace('_', ' ').title().replace(' ', '')[1:]}Ids"
            if entity_type == "event_api": id_param = "eventApiIds"
            
            try:
                versions = await _call_mcp(session, version_tool, {id_param: [item["id"]]})
                if versions and isinstance(versions, list) and len(versions) > 0:
                    item["latest_version_id"] = versions[0].get("id")
                    item["latest_version"] = versions[0].get("version")
            except Exception:
                pass
        enriched_results.append(item)

    return {"result": enriched_results}


async def _get_schema_content(session: ClientSession, entity_id: str) -> dict:
    """Smart router to extract actual JSON/AVRO schema content from various ID types."""
    schema_version_id = None
    
    # Helper to fetch by both 'ids' and 'parentIds'
    async def _fetch(tool, id_param):
        res = await _call_mcp(session, tool, {"ids": [entity_id]})
        if res and isinstance(res, list) and len(res) > 0: return res
        res = await _call_mcp(session, tool, {id_param: [entity_id]})
        if res and isinstance(res, list) and len(res) > 0: return res
        return []

    # 1. Could it be an Event? (Event Version or Base Event ID)
    evt_vers = await _fetch("getEventVersions", "eventIds")
    if evt_vers:
        # Get schemaVersionId from the event version
        schema_version_id = evt_vers[0].get("schemaVersionId")
        
    if not schema_version_id:
        # 2. Could it be a Schema? (Schema Version or Base Schema ID)
        sch_vers = await _fetch("getSchemaVersions", "schemaIds")
        if sch_vers:
            # We already have the schema version
            return {"result": sch_vers[0].get("content", "Schema found but it has no text content.")}
            
    if not schema_version_id:
        # 3. Was it explicitly passed a schemaVersionId?
        schema_version_id = entity_id

    # Now fetch the schema content using the schema_version_id
    res = await _call_mcp(session, "getSchemaVersions", {"ids": [schema_version_id]})
    if res and isinstance(res, list) and len(res) > 0:
        content = res[0].get("content")
        return {"result": content if content else "Schema found but it has no text content."}
        
    return {"error": f"Could not find schema content for ID {entity_id}. Ensure the ID is a valid Event or Schema."}


async def _get_relationships(session: ClientSession, entity_id: str, relationship_type: str) -> dict:
    """Executes the get_entity_relationships logic by chaining Solace tools."""
    
    if relationship_type == "applications":
        # Find all apps within a domain
        data = await _call_mcp(session, "getApplications", {"applicationDomainId": entity_id})
        # Keep it clean for the LLM
        clean_apps = [{"id": a["id"], "name": a["name"]} for a in data if "id" in a and "name" in a]
        return {"result": clean_apps}
        
    elif relationship_type in ["produced_events", "consumed_events"]:
        event_version_ids = []
        
        # Helper to fetch version by trying both 'ids' (version ID) and 'XXXIds' (base ID)
        async def _fetch_versions(tool_name, base_id_param):
            res = await _call_mcp(session, tool_name, {"ids": [entity_id]})
            if res and isinstance(res, list) and len(res) > 0: return res
            res = await _call_mcp(session, tool_name, {base_id_param: [entity_id]})
            if res and isinstance(res, list) and len(res) > 0: return res
            return []

        # 1. Try treating entity_id as an Application
        app_versions = await _fetch_versions("getApplicationVersions", "applicationIds")
        if app_versions:
            latest = app_versions[0]
            if relationship_type == "produced_events":
                event_version_ids = latest.get("declaredProducedEventVersionIds", [])
            else:
                event_version_ids = latest.get("declaredConsumedEventVersionIds", [])
                
        # 2. Try treating entity_id as an Event API if it wasn't an Application
        if not app_versions:
            api_versions = await _fetch_versions("getEventApiVersions", "eventApiIds")
            if api_versions:
                latest = api_versions[0]
                if relationship_type == "produced_events":
                    event_version_ids = latest.get("producedEventVersionIds", [])
                else:
                    event_version_ids = latest.get("consumedEventVersionIds", [])
                    
        if not event_version_ids:
            return {"result": []}
            
        # 3. Solace requires us to fetch the actual event names using getEventVersions
        resolved_events = []
        for ev_id in event_version_ids:
            # We fetch the specific event version to get its parent Event ID, but we can also just
            # return the event version data. Let's fetch the event version.
            ev_data = await _call_mcp(session, "getEventVersions", {"ids": [ev_id]})
            if ev_data:
                ev = ev_data[0]
                resolved_events.append({
                    "version_id": ev.get("id"),
                    "event_id": ev.get("eventId"),
                    "version": ev.get("version"),
                    "description": ev.get("description", "")
                })
                
        # 4. To get the pretty event NAME, we could query getEvent using the event_id, but the version often suffices.
        # For a truly complete answer, let's look up the parent Event to get the name.
        for ev in resolved_events:
            parent_event = await _call_mcp(session, "getEvents", {"ids": [ev["event_id"]]})
            if parent_event:
                ev["name"] = parent_event[0].get("name", "Unknown")

        return {"result": resolved_events}

    elif relationship_type == "event_apis":
        prod_vers = await _call_mcp(session, "getEventApiProductVersions", {"eventApiProductIds": [entity_id]})
        if not prod_vers or isinstance(prod_vers, dict): return {"result": []}
        api_ver_ids = prod_vers[0].get("eventApiVersionIds", [])
        if not api_ver_ids: return {"result": []}
        
        apis = []
        for api_vid in api_ver_ids:
            api_ver = await _call_mcp(session, "getEventApiVersions", {"ids": [api_vid]})
            if api_ver and not isinstance(api_ver, dict):
                apis.append({"version_id": api_vid, "event_api_id": api_ver[0].get("eventApiId"), "version": api_ver[0].get("version")})
        return {"result": apis}

    elif relationship_type == "consuming_applications":
        # Forward to impact analysis. Assumes entity_id is a parent ID and fetches latest version.
        vers = await _call_mcp(session, "getEventApiVersions", {"eventApiIds": [entity_id]})
        if not vers or isinstance(vers, dict): return {"result": []}
        
        produced_events = vers[0].get("producedEventVersionIds", [])
        apps = await _call_mcp(session, "getApplicationVersions", {})
        consuming_apps = []
        
        if isinstance(apps, list):
            for app in apps:
                app_consumed = app.get("declaredConsumedEventVersionIds", [])
                if any(ev_id in app_consumed for ev_id in produced_events):
                    consuming_apps.append({
                        "version_id": app.get("id"),
                        "application_id": app.get("applicationId"),
                        "version": app.get("version")
                    })
                    
        return {"result": consuming_apps}

    return {"error": f"Unsupported relationship_type: {relationship_type}"}


async def _create_entity(session: ClientSession, entity_type: str, name: str, domain_name: str = None, enum_values: list = None) -> dict:
    """Executes the create_solace_entity logic."""
    # 1. Check if it exists
    existing = await _search_entity(session, entity_type, name)
    if existing.get("result") and len(existing["result"]) > 0:
        return {"error": f"{entity_type.capitalize()} '{name}' already exists. Use create_solace_entity_version to add a new version."}

    # 2. Create Domain (no parent required)
    if entity_type == "domain":
        data = await _call_mcp(session, "createApplicationDomain", {"name": name})
        return {"result": data}

    # 3. For app and event, we need a domain
    if not domain_name:
        return {"error": "domain_name is required for applications and events."}

    # Resolve domain ID
    domain_search = await _search_entity(session, "domain", domain_name)
    if not domain_search.get("result") or len(domain_search["result"]) == 0:
        return {"error": f"Domain '{domain_name}' not found."}
    
    domain_id = domain_search["result"][0]["id"]

    # 4. Create entity and its initial version
    if entity_type == "application":
        data = await _call_mcp(session, "createApplication", {
            "name": name,
            "applicationDomainId": domain_id,
            "applicationType": "standard",
            "brokerType": "solace"
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        app_id = entity.get("id")
        if not app_id:
            return {"error": f"Created app but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createApplicationVersion", {
            "applicationId": app_id,
            "version": "0.1.0"
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    elif entity_type == "event":
        data = await _call_mcp(session, "createEvent", {
            "name": name,
            "applicationDomainId": domain_id
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        evt_id = entity.get("id")
        if not evt_id:
            return {"error": f"Created event but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createEventVersion", {
            "eventId": evt_id,
            "version": "0.1.0"
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    elif entity_type == "event_api":
        data = await _call_mcp(session, "createEventApi", {
            "name": name,
            "applicationDomainId": domain_id,
            "brokerType": "solace"
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        evt_api_id = entity.get("id")
        if not evt_api_id:
            return {"error": f"Created event api but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createEventApiVersion", {
            "eventApiId": evt_api_id,
            "version": "0.1.0"
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    elif entity_type == "event_api_product":
        data = await _call_mcp(session, "createEventApiProduct", {
            "name": name,
            "applicationDomainId": domain_id,
            "brokerType": "solace"
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        evt_api_prod_id = entity.get("id")
        if not evt_api_prod_id:
            return {"error": f"Created event api product but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createEventApiProductVersion", {
            "eventApiProductId": evt_api_prod_id,
            "version": "0.1.0"
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    elif entity_type == "schema":
        data = await _call_mcp(session, "createSchema", {
            "name": name,
            "applicationDomainId": domain_id,
            "schemaType": "jsonSchema"  # Defaulting to jsonSchema, can be enhanced later
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        schema_id = entity.get("id")
        if not schema_id:
            return {"error": f"Created schema but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createSchemaVersion", {
            "schemaId": schema_id,
            "version": "0.1.0"
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    elif entity_type == "enum":
        if not enum_values:
            return {"error": "enum_values is required when creating an enum"}
            
        data = await _call_mcp(session, "createEnum", {
            "name": name,
            "applicationDomainId": domain_id
        })
        entity = data[0] if isinstance(data, list) and len(data) > 0 else data
        enum_id = entity.get("id")
        if not enum_id:
            return {"error": f"Created enum but couldn't get ID. Response: {data}"}

        ver_data = await _call_mcp(session, "createEnumVersion", {
            "enumId": enum_id,
            "version": "0.1.0",
            "values": [{"value": v} for v in enum_values]
        })
        return {"result": {"entity": entity, "initial_version": ver_data}}

    return {"error": f"Unsupported entity_type: {entity_type}"}


async def _create_version(session: ClientSession, entity_type: str, entity_id: str, version: str, enum_values: list = None) -> dict:
    """Executes the create_solace_entity_version logic."""
    if entity_type == "application":
        ver_data = await _call_mcp(session, "createApplicationVersion", {
            "applicationId": entity_id,
            "version": version
        })
        return {"result": ver_data}
    elif entity_type == "event":
        ver_data = await _call_mcp(session, "createEventVersion", {
            "eventId": entity_id,
            "version": version
        })
        return {"result": ver_data}
    elif entity_type == "event_api":
        ver_data = await _call_mcp(session, "createEventApiVersion", {
            "eventApiId": entity_id,
            "version": version
        })
        return {"result": ver_data}
    elif entity_type == "event_api_product":
        ver_data = await _call_mcp(session, "createEventApiProductVersion", {
            "eventApiProductId": entity_id,
            "version": version
        })
        return {"result": ver_data}
    elif entity_type == "schema":
        ver_data = await _call_mcp(session, "createSchemaVersion", {
            "schemaId": entity_id,
            "version": version
        })
        return {"result": ver_data}
    elif entity_type == "enum":
        if not enum_values:
            return {"error": "enum_values is required when versioning an enum"}
            
        ver_data = await _call_mcp(session, "createEnumVersion", {
            "enumId": entity_id,
            "version": version,
            "values": [{"value": v} for v in enum_values]
        })
        return {"result": ver_data}
    
    return {"error": f"Unsupported entity_type: {entity_type}"}


async def _delete_entity(session: ClientSession, entity_type: str, entity_id: str) -> dict:
    """Executes the delete_solace_entity logic."""
    if entity_type == "domain":
        res = await _call_mcp(session, "deleteApplicationDomain", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted application domain with ID {entity_id}"}
    elif entity_type == "application":
        res = await _call_mcp(session, "deleteApplication", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted application with ID {entity_id}"}
    elif entity_type == "event":
        res = await _call_mcp(session, "deleteEvent", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event with ID {entity_id}"}
    elif entity_type == "event_api":
        res = await _call_mcp(session, "deleteEventApi", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event api with ID {entity_id}"}
    elif entity_type == "event_api_product":
        res = await _call_mcp(session, "deleteEventApiProduct", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event api product with ID {entity_id}"}
    elif entity_type == "schema":
        res = await _call_mcp(session, "deleteSchema", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted schema with ID {entity_id}"}
    elif entity_type == "enum":
        res = await _call_mcp(session, "deleteEnum", {"id": entity_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted enum with ID {entity_id}"}
    
    return {"error": f"Unsupported entity_type for deletion: {entity_type}"}


async def _delete_version(session: ClientSession, entity_type: str, version_id: str) -> dict:
    """Executes the delete_solace_entity_version logic."""
    if entity_type == "application":
        res = await _call_mcp(session, "deleteApplicationVersion", {"versionId": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted application version {version_id}"}
    elif entity_type == "event":
        res = await _call_mcp(session, "deleteEventVersion", {"id": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event version {version_id}"}
    elif entity_type == "event_api":
        res = await _call_mcp(session, "deleteEventApiVersion", {"versionId": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event api version {version_id}"}
    elif entity_type == "event_api_product":
        res = await _call_mcp(session, "deleteEventApiProductVersion", {"versionId": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted event api product version {version_id}"}
    elif entity_type == "schema":
        res = await _call_mcp(session, "deleteSchemaVersion", {"id": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted schema version {version_id}"}
    elif entity_type == "enum":
        res = await _call_mcp(session, "deleteEnumVersion", {"id": version_id})
        if isinstance(res, dict) and "error" in res: return res
        return {"result": f"Successfully deleted enum version {version_id}"}
    
    return {"error": f"Unsupported entity_type for version deletion: {entity_type}"}


async def _duplicate_entity(session: ClientSession, entity_type: str, source_entity_id: str, new_name: str) -> dict:
    get_tool = f"get{entity_type.replace('_', ' ').title().replace(' ', '')}s"
    if entity_type == "event_api": get_tool = "getEventApis"
    
    source_entity_res = await _call_mcp(session, get_tool, {"ids": [source_entity_id]})
    if not source_entity_res or isinstance(source_entity_res, dict):
        return {"error": f"Source entity {source_entity_id} not found."}
    source_entity = source_entity_res[0]

    create_payload = {"name": new_name}
    for key in ["applicationDomainId", "brokerType", "applicationType", "schemaType"]:
        if key in source_entity: create_payload[key] = source_entity[key]
    
    create_tool = f"create{entity_type.replace('_', ' ').title().replace(' ', '')}"
    new_entity_res = await _call_mcp(session, create_tool, create_payload)
    if isinstance(new_entity_res, dict) and "error" in new_entity_res: return new_entity_res
    new_entity = new_entity_res[0] if isinstance(new_entity_res, list) else new_entity_res
    new_entity_id = new_entity.get("id")

    if entity_type == "domain": return {"result": "Duplicated domain", "entity": new_entity}

    get_ver_tool = f"get{entity_type.replace('_', ' ').title().replace(' ', '')}Versions"
    id_param = f"{entity_type.replace('_', ' ').title().replace(' ', '')[:1].lower() + entity_type.replace('_', ' ').title().replace(' ', '')[1:]}Ids"
    if entity_type == "event_api": id_param = "eventApiIds"
    
    source_vers = await _call_mcp(session, get_ver_tool, {id_param: [source_entity_id]})
    if not source_vers or isinstance(source_vers, dict):
        return {"result": "Duplicated entity, no versions found.", "entity": new_entity}
    
    source_ver = source_vers[0]
    create_ver_payload = {"version": "0.1.0", id_param[:-1]: new_entity_id}
    
    for key in ["eventApiVersionIds", "declaredProducedEventVersionIds", "declaredConsumedEventVersionIds", "producedEventVersionIds", "consumedEventVersionIds", "schemaVersionId", "schemaId"]:
        if key in source_ver: create_ver_payload[key] = source_ver[key]

    create_ver_tool = f"create{entity_type.replace('_', ' ').title().replace(' ', '')}Version"
    new_ver_res = await _call_mcp(session, create_ver_tool, create_ver_payload)

    return {"result": f"Duplicated {entity_type} successfully.", "new_entity": new_entity, "new_version": new_ver_res}


async def _update_relationship(session: ClientSession, entity_type: str, version_id: str, action: str, target_type: str, target_version_id: str) -> dict:
    get_ver_tool = f"get{entity_type.replace('_', ' ').title().replace(' ', '')}Versions"
    source_vers = await _call_mcp(session, get_ver_tool, {"ids": [version_id]})
    if not source_vers or isinstance(source_vers, dict): return {"error": f"Version {version_id} not found."}
    
    source_ver = source_vers[0]
    array_key = None
    if entity_type == "event_api_product" and target_type == "event_api": array_key = "eventApiVersionIds"
    elif entity_type == "event_api" and target_type == "event": array_key = "producedEventVersionIds" 
    elif entity_type == "application" and target_type == "event": array_key = "declaredProducedEventVersionIds"
    
    if not array_key: return {"error": f"Mapping between {entity_type} and {target_type} unsupported."}

    current_array = source_ver.get(array_key, [])
    if action == "add" and target_version_id not in current_array: current_array.append(target_version_id)
    elif action == "remove" and target_version_id in current_array: current_array.remove(target_version_id)

    patch_tool = f"update{entity_type.replace('_', ' ').title().replace(' ', '')}Version"
    id_param = "versionId" if entity_type != "event" else "id"
    patch_payload = {id_param: version_id, array_key: current_array}
    
    return {"result": await _call_mcp(session, patch_tool, patch_payload)}


async def _get_impact(session: ClientSession, entity_type: str, version_id: str) -> dict:
    impacted = []
    
    if entity_type == "event":
        # Check Event APIs
        apis = await _call_mcp(session, "getEventApiVersions", {})
        if isinstance(apis, list):
            for api in apis:
                if version_id in api.get("producedEventVersionIds", []) or version_id in api.get("consumedEventVersionIds", []):
                    api["type"] = "eventApiVersion"
                    # Fetch parent to get name
                    parent_id = api.get("eventApiId")
                    if parent_id:
                        parent = await _call_mcp(session, "getEventApis", {"ids": [parent_id]})
                        if isinstance(parent, list) and len(parent) > 0:
                            api["name"] = parent[0].get("name")
                    
                    # Proactively resolve Event API Product names if present, because the AI 
                    # often sees these IDs and stops without doing the second hop!
                    if api.get("declaredEventApiProductVersionIds"):
                        api["declaredEventApiProductNames"] = []
                        for prod_vid in api["declaredEventApiProductVersionIds"]:
                            prod_ver = await _call_mcp(session, "getEventApiProductVersions", {"ids": [prod_vid]})
                            if prod_ver and len(prod_ver) > 0:
                                prod_parent_id = prod_ver[0].get("eventApiProductId")
                                if prod_parent_id:
                                    prod_parent = await _call_mcp(session, "getEventApiProducts", {"ids": [prod_parent_id]})
                                    if prod_parent and len(prod_parent) > 0:
                                        api["declaredEventApiProductNames"].append(prod_parent[0].get("name"))
                                        
                    impacted.append(api)
                    
        # Check Applications
        apps = await _call_mcp(session, "getApplicationVersions", {})
        if isinstance(apps, list):
            for app in apps:
                if version_id in app.get("declaredProducedEventVersionIds", []) or version_id in app.get("declaredConsumedEventVersionIds", []):
                    app["type"] = "applicationVersion"
                    parent_id = app.get("applicationId")
                    if parent_id:
                        parent = await _call_mcp(session, "getApplications", {"ids": [parent_id]})
                        if isinstance(parent, list) and len(parent) > 0:
                            app["name"] = parent[0].get("name")
                    impacted.append(app)
                    
    elif entity_type == "event_api":
        # Check Event API Products
        prods = await _call_mcp(session, "getEventApiProductVersions", {})
        if isinstance(prods, list):
            for prod in prods:
                if version_id in prod.get("eventApiVersionIds", []):
                    prod["type"] = "eventApiProductVersion"
                    parent_id = prod.get("eventApiProductId")
                    if parent_id:
                        parent = await _call_mcp(session, "getEventApiProducts", {"ids": [parent_id]})
                        if isinstance(parent, list) and len(parent) > 0:
                            prod["name"] = parent[0].get("name")
                    impacted.append(prod)
                    
    elif entity_type == "schema":
        # Check Events
        evts = await _call_mcp(session, "getEventVersions", {})
        if isinstance(evts, list):
            for evt in evts:
                if version_id == evt.get("schemaVersionId"):
                    evt["type"] = "eventVersion"
                    parent_id = evt.get("eventId")
                    if parent_id:
                        parent = await _call_mcp(session, "getEvents", {"ids": [parent_id]})
                        if isinstance(parent, list) and len(parent) > 0:
                            evt["name"] = parent[0].get("name")
                    impacted.append(evt)
                    
    return {"result": impacted}


# ── The Interceptor ────────────────────────────────────────────────────────
async def execute_smart_tool(session: ClientSession, tool_name: str, args: dict) -> str:
    """Routes the LLM's generic tool call to the Python mapping engine."""
    
    try:
        if tool_name == "search_solace_entity":
            result = await _search_entity(session, args.get("entity_type"), args.get("name"), args.get("domain_name"), args.get("entity_id"))
        elif tool_name == "get_schema_content":
            result = await _get_schema_content(session, args.get("entity_id"))
        elif tool_name == "get_entity_relationships":
            result = await _get_relationships(session, args.get("entity_id"), args.get("relationship_type"))
        elif tool_name == "create_solace_entity":
            result = await _create_entity(session, args.get("entity_type"), args.get("name"), args.get("domain_name"), args.get("enum_values"))
        elif tool_name == "create_solace_entity_version":
            result = await _create_version(session, args.get("entity_type"), args.get("entity_id"), args.get("version"), args.get("enum_values"))
        elif tool_name == "delete_solace_entity":
            result = await _delete_entity(session, args.get("entity_type"), args.get("entity_id"))
        elif tool_name == "delete_solace_entity_version":
            result = await _delete_version(session, args.get("entity_type"), args.get("version_id"))
        elif tool_name == "duplicate_solace_entity":
            result = await _duplicate_entity(session, args.get("entity_type"), args.get("source_entity_id"), args.get("new_name"))
        elif tool_name == "update_entity_relationship":
            result = await _update_relationship(session, args.get("entity_type"), args.get("version_id"), args.get("action"), args.get("target_type"), args.get("target_version_id"))
        elif tool_name == "get_entity_impact":
            result = await _get_impact(session, args.get("entity_type"), args.get("version_id"))
        else:
            return json.dumps({"error": f"Unknown smart tool: {tool_name}"})
            
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": f"Execution failed: {str(exc)}"})
