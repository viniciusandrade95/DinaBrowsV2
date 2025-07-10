# main.py
# Versão simplificada que mantém a estrutura original, mas responde apenas "Estou vivo".

import os
import httpx
import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente
load_dotenv()

# --- Validação de Configuração ---
class Config:
    """Centraliza a configuração essencial para o webhook funcionar."""
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") # ID do seu número de envio
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    @classmethod
    def validate(cls):
        """Valida se as configurações obrigatórias estão presentes"""
        required = {
            "WHATSAPP_TOKEN": cls.WHATSAPP_TOKEN, 
            "PHONE_NUMBER_ID": cls.PHONE_NUMBER_ID,
            "VERIFY_TOKEN": cls.VERIFY_TOKEN
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            error_msg = f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing)}"
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

# Validar configuração
Config.validate()

# --- App FastAPI com lifecycle management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando aplicação em modo {Config.ENVIRONMENT}")
    yield
    logger.info("Encerrando aplicação")

app = FastAPI(title="WhatsApp Bot 'Estou Vivo'", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Classes de Serviço ---

class WhatsAppService:
    """Serviço responsável por enviar mensagens via API do WhatsApp."""
    @staticmethod
    async def send_message(to_number: str, message_text: str) -> bool:
        url = f"https://graph.facebook.com/v18.0/{Config.PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {Config.WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message_text}
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                logger.info(f"Mensagem enviada para {to_number[:6]}****")
                return True
        except httpx.HTTPError as e:
            logger.error(f"Erro HTTP ao enviar mensagem: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar mensagem: {e}")
            return False

# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "online", "service": "WhatsApp Bot 'Estou Vivo'", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    # Health check simplificado que não depende de serviços externos.
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == Config.VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso")
        return Response(content=challenge, media_type="text/plain")
    else:
        logger.warning(f"Tentativa de verificação inválida: mode={mode}, token={token}")
        raise HTTPException(status_code=403, detail="Verificação falhou")

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    if Config.ENVIRONMENT == "development":
        logger.debug(f"Webhook recebido: {body}")
    
    try:
        # Extrai a informação da mensagem
        value = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return Response(status_code=200)
        
        message = messages[0]
        from_number = message.get("from")
        message_text = message.get("text", {}).get("body")

        # Se não for uma mensagem de texto válida, ignora
        if not from_number or not message_text:
            return Response(status_code=200)

        # A única lógica aqui é enviar a resposta fixa.
        logger.info(f"Recebida mensagem de {from_number}. Respondendo 'Estou vivo'.")
        
        reply_text = "Estou vivo"
        await WhatsAppService.send_message(from_number, reply_text)
        
    except Exception as e:
        logger.error(f"Erro crítico no webhook: {str(e)}", exc_info=True)
    
    # Responde sempre 200 para a API do WhatsApp para confirmar o recebimento.
    return Response(status_code=200)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Erro não tratado: {str(exc)}", exc_info=True)
    return Response(content="Erro interno do servidor", status_code=500)
