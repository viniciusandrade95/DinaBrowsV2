import os
import httpx
import openai
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from contextlib import asynccontextmanager

# Configurar logging para produção
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente
load_dotenv()

# --- Validação de Configuração ---
class Config:
    """Centraliza toda a configuração da aplicação"""
    # WhatsApp
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    
    # AI
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # Ambiente
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    TEST_TENANT_ID = os.getenv("TEST_TENANT_ID")  # Opcional
    
    @classmethod
    def validate(cls):
        """Valida se todas as configurações obrigatórias estão presentes"""
        required = {
            "WHATSAPP_TOKEN": cls.WHATSAPP_TOKEN,
            "PHONE_NUMBER_ID": cls.PHONE_NUMBER_ID,
            "VERIFY_TOKEN": cls.VERIFY_TOKEN,
            "TOGETHER_API_KEY": cls.TOGETHER_API_KEY,
            "SUPABASE_URL": cls.SUPABASE_URL,
            "SUPABASE_KEY": cls.SUPABASE_KEY
        }
        
        missing = [key for key, value in required.items() if not value]
        
        if missing:
            error_msg = f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing)}"
            logger.critical(error_msg)
            raise RuntimeError(error_msg)
        
        if cls.ENVIRONMENT == "development" and not cls.TEST_TENANT_ID:
            logger.warning("TEST_TENANT_ID não definido em ambiente de desenvolvimento")

# Validar configuração
Config.validate()

# Inicializar Supabase
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# --- App FastAPI com lifecycle management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    logger.info(f"Iniciando aplicação em modo {Config.ENVIRONMENT}")
    yield
    logger.info("Encerrando aplicação")

app = FastAPI(
    title="WhatsApp Bot API",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS para produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Classe do Bot Melhorada ---
class BrowStudioBot:
    def __init__(self, studio_info: Dict[str, Any], api_key: str):
        if not api_key:
            raise ValueError("A chave da API da IA não foi fornecida.")
        
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.together.xyz/v1"
        )
        self.studio_info = studio_info
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Constrói o prompt do sistema com informações do estúdio"""
        services = self.studio_info.get('services', [])
        services_text = ""
        
        if services:
            for service in services:
                name = service.get('service_name', 'Serviço')
                price = service.get('price', 'Consulte')
                duration = service.get('duration', 'A combinar')
                services_text += f"- {name}: R$ {price} (duração: {duration})\n"
        else:
            services_text = "- Entre em contato para conhecer nossos serviços\n"
        
        return f"""Você é uma atendente virtual do {self.studio_info.get('business_name', 'nosso estúdio')}.

INFORMAÇÕES DO NEGÓCIO:
- Horário: {self.studio_info.get('working_hours', 'Segunda a Sexta, 9h às 18h')}
- Telefone: {self.studio_info.get('business_phone', 'Consulte')}
- Endereço: {self.studio_info.get('address', 'Consulte')}

SERVIÇOS OFERECIDOS:
{services_text}

INSTRUÇÕES:
1. Responda APENAS em português brasileiro
2. Seja simpática, profissional e prestativa
3. Para agendamentos, direcione para o WhatsApp
4. Se não souber algo, sugira contato direto
5. Mantenha respostas concisas mas informativas
6. Use emojis com moderação para tornar a conversa mais amigável"""

    async def get_response(self, user_message: str) -> str:
        """Gera resposta usando a API de IA"""
        try:
            response = self.client.chat.completions.create(
                model=Config.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erro na API de IA: {str(e)}", exc_info=True)
            return (
                "Desculpe, estou com um problema técnico no momento. 😔\n"
                f"Por favor, entre em contato diretamente: {self.studio_info.get('business_phone', 'nosso WhatsApp')}"
            )

# --- Serviços do WhatsApp ---
class WhatsAppService:
    @staticmethod
    async def send_message(to_number: str, message_text: str) -> bool:
        """Envia mensagem via WhatsApp Business API"""
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
        except httpx.TimeoutException:
            logger.error(f"Timeout ao enviar mensagem para {to_number[:6]}****")
            return False
        except httpx.HTTPError as e:
            logger.error(f"Erro HTTP ao enviar mensagem: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar mensagem: {e}")
            return False

# --- Serviços do Supabase ---
class DatabaseService:
    @staticmethod
    async def get_tenant_data(tenant_id: str) -> Optional[Dict[str, Any]]:
        """Busca dados do tenant com tratamento de erros"""
        try:
            response = supabase.table("tenants").select("*, services(*)").eq("id", tenant_id).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"Erro ao buscar tenant {tenant_id}: {str(e)}")
            return None
    
    @staticmethod
    async def update_message_count(tenant_id: str, new_count: int) -> bool:
        """Atualiza contador de mensagens"""
        try:
            supabase.table("tenants").update({
                "message_count": new_count,
                "last_message_at": datetime.utcnow().isoformat()
            }).eq("id", tenant_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar contador: {str(e)}")
            return False
    
    @staticmethod
    async def save_message_history(
        tenant_id: str,
        phone_number: str,
        user_message: str,
        bot_response: str
    ) -> bool:
        """Salva histórico de mensagens"""
        try:
            supabase.table("message_history").insert({
                "tenant_id": tenant_id,
                "phone_number": phone_number,
                "user_message": user_message[:1000],  # Limita tamanho
                "bot_response": bot_response[:1000],
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {str(e)}")
            return False

# --- Função para mapear número para tenant ---
async def get_tenant_id_from_message(message_data: Dict[str, Any]) -> Optional[str]:
    """
    Determina o tenant_id baseado na mensagem recebida.
    Em produção, isso pode usar o número do destinatário ou outros metadados.
    """
    if Config.ENVIRONMENT == "development":
        return Config.TEST_TENANT_ID
    
    # TODO: Implementar lógica de produção
    # Exemplo: buscar na tabela phone_mappings
    # phone_to = message_data.get("to")
    # result = supabase.table("phone_mappings").select("tenant_id").eq("phone", phone_to).single().execute()
    # return result.data.get("tenant_id") if result.data else None
    
    return None

# --- Endpoints ---
@app.get("/")
async def root():
    """Endpoint raiz com informações básicas"""
    return {
        "status": "online",
        "service": "WhatsApp Bot API",
        "version": "1.0.0",
        "environment": Config.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    """Verifica saúde da aplicação e dependências"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "whatsapp": bool(Config.WHATSAPP_TOKEN and Config.PHONE_NUMBER_ID),
            "database": False,
            "ai": bool(Config.TOGETHER_API_KEY)
        }
    }
    
    # Testa conexão com Supabase
    try:
        supabase.table("tenants").select("id").limit(1).execute()
        health_status["checks"]["database"] = True
    except:
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verifica o webhook do WhatsApp"""
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
    """Processa webhooks do WhatsApp"""
    try:
        body = await request.json()
        
        # Log apenas em desenvolvimento
        if Config.ENVIRONMENT == "development":
            logger.debug(f"Webhook recebido: {body}")
        
        # Validação inicial
        if body.get("object") != "whatsapp_business_account":
            return Response(status_code=200)
        
        # Extração segura dos dados
        entry = body.get("entry", [])
        if not entry:
            return Response(status_code=200)
        
        changes = entry[0].get("changes", [])
        if not changes:
            return Response(status_code=200)
        
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return Response(status_code=200)
        
        # Processa apenas a primeira mensagem
        message = messages[0]
        message_id = message.get("id")
        from_number = message.get("from")
        message_type = message.get("type")
        
        # Processa apenas mensagens de texto
        if message_type != "text":
            logger.info(f"Tipo de mensagem não suportado: {message_type}")
            return Response(status_code=200)
        
        message_text = message.get("text", {}).get("body", "").strip()
        
        if not from_number or not message_text:
            return Response(status_code=200)
        
        # Obtém o tenant_id
        tenant_id = await get_tenant_id_from_message(value)
        
        if not tenant_id:
            logger.error("Não foi possível determinar o tenant_id")
            await WhatsAppService.send_message(
                from_number,
                "Desculpe, não consegui identificar sua empresa. Por favor, verifique o número."
            )
            return Response(status_code=200)
        
        # Busca dados do tenant
        tenant_data = await DatabaseService.get_tenant_data(tenant_id)
        
        if not tenant_data:
            logger.error(f"Tenant {tenant_id} não encontrado")
            return Response(status_code=200)
        
        # Verifica limites
        message_count = tenant_data.get("message_count", 0)
        message_limit = tenant_data.get("message_limit", 100)
        
        if message_count >= message_limit:
            logger.warning(f"Limite atingido para {tenant_data.get('business_name')}")
            await WhatsAppService.send_message(
                from_number,
                "Olá! 👋 Nosso atendimento automático atingiu o limite diário.\n"
                "Um de nossos atendentes irá responder em breve. Obrigado! 🙏"
            )
            return Response(status_code=200)
        
        # Gera e envia resposta
        bot = BrowStudioBot(studio_info=tenant_data, api_key=Config.TOGETHER_API_KEY)
        reply_text = await bot.get_response(message_text)
        
        success = await WhatsAppService.send_message(from_number, reply_text)
        
        if success:
            # Atualiza contador
            await DatabaseService.update_message_count(tenant_id, message_count + 1)
            
            # Salva histórico
            await DatabaseService.save_message_history(
                tenant_id, from_number, message_text, reply_text
            )
        
    except Exception as e:
        logger.error(f"Erro crítico no webhook: {str(e)}", exc_info=True)
    
    # Sempre retorna 200 para evitar retry do WhatsApp
    return Response(status_code=200)

# --- Tratamento de erros global ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura erros não tratados"""
    logger.error(f"Erro não tratado: {str(exc)}", exc_info=True)
    return Response(
        content={"error": "Erro interno do servidor"},
        status_code=500
    )
