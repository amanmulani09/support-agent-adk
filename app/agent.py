from google.adk.agents import Agent
from typing import Any

def lookup_order(order_id:str) -> dict[str,Any]:
    
    orders:dict[str,Any] = {
        "12345": {
            "order_id": "12345",
            "status": "shipped",
            "carrier": "DHL",
            "estimated_delivery": "2026-09-10",
        },
        "67890": {
            "order_id": "67890",
            "status": "processing",
            "carrier": None,
            "estimated_delivery": None,
        },
    }
    
    order = orders.get(order_id)
    
    if not order:
        return {
            "found":False,
            "message" : "order not found"
        }
    
    return {
        "found":True,
        **order
    }

root_agent = Agent(
    name="support_agent",
    model="gemini-2.5-flash",
    instruction=""""
    You are a helpful customer support agent.

    Your job is to:
    - Answer customer support questions clearly.
    - Be concise and friendly.
    - Never invent order information.
    - Use lookup_order whenever the customer asks about an order.
    - If an order cannot be found, explain that clearly.
    """,
    tools=[lookup_order]
    
)