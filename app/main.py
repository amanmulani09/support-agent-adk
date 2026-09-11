from fastapi import FastAPI
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
class SupportRequest(BaseModel):
    message:str
    user_id:str
    
class SupportResponse(BaseModel):
    response:str

app = FastAPI()

@app.get('/')
async def root():
    return {"status":"ok"}


@app.post('/health')
async def health():
    return {"status":"healthy"}


session_service = InMemorySessionService()

runner = Runner(
    app_name="customer_support_agent",
    agent=root_agent,
    session_service=session_service
)


@app.post('/support', response_model=SupportResponse)
async def get_support(req:SupportRequest):
    
    session = await session_service.create_session(
        app_name="customer_support_agent",
        user_id=req.user_id
    )
    
    content = types.Content(
        role="user",
        parts=[
            types.Part(text=req.message)
        ]
    )
    
    response_text:str = ""
    
    async for event in runner.run_async(
        user_id=req.user_id,
        session_id=session.id,
        new_message=content
    ):
        if event.is_final_response():
            response_text = event.content.parts[0].text
            
    return {
        "response":response_text
    }
    
    