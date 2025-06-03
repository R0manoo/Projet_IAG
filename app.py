import streamlit as st
import os
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
import json

# Imports pour le calendrier
from streamlit_calendar import calendar

# Imports de tes modules
from scrap_edt import get_edt_semaine_json
from schedule_functions import (
    load_schedule_data, 
    get_courses_by_date_range, 
    get_courses_by_subject, 
    get_free_time_slots, 
    get_next_course,
    TOOLS,
    AVAILABLE_FUNCTIONS
)
from openai import OpenAI

# Charger les variables d'environnement
load_dotenv()

# Configuration de l'API OpenAI
def check_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY non trouvée dans les variables d'environnement")
        st.info("Ajoutez votre clé API OpenAI dans le fichier .env")
        st.stop()
    return api_key

def ensure_schedule_data(user_id):
    """S'assure que les données d'emploi du temps sont disponibles"""
    json_dir = "json_schedules"
    json_file = os.path.join(json_dir, f"{user_id}_edt.json")
    
    if not os.path.exists(json_file):
        st.info(f"📥 Récupération de l'emploi du temps pour {user_id}...")
        try:
            get_edt_semaine_json(user_id)
            st.success("✅ Emploi du temps mis à jour !")
            return True
        except Exception as e:
            st.error(f"❌ Erreur lors de la récupération : {e}")
            return False
    return True

import logging

# Configurer les logs au début de app.py
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_response(prompt: str, user_id: str) -> str:
    """Génère une réponse en utilisant les function calling d'OpenAI"""
    try:
        from schedule_functions import AVAILABLE_FUNCTIONS, TOOLS
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        logger.info(f"🚀 Génération de réponse pour: {prompt}")
        logger.info(f"👤 User ID: {user_id}")
        logger.info(f"🔧 Nombre d'outils disponibles: {len(TOOLS)}")
        
        # Contexte temporel
        from datetime import datetime, timedelta
        import locale
        
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'French')
            except:
                pass
        
        maintenant = datetime.now()
        aujourd_hui = maintenant.date()
        demain = aujourd_hui + timedelta(days=1)
        
        jours_depuis_lundi = aujourd_hui.weekday()
        debut_semaine = aujourd_hui - timedelta(days=jours_depuis_lundi)
        fin_semaine = debut_semaine + timedelta(days=6)
        
        debut_semaine_prochaine = debut_semaine + timedelta(days=7)
        fin_semaine_prochaine = debut_semaine_prochaine + timedelta(days=6)
        
        system_message = f"""
        Tu es un assistant de planification d'études expert pour {user_id}.

        ⚠️ RÈGLE ABSOLUE : Tu DOIS TOUJOURS appeler les fonctions disponibles pour récupérer les vraies données avant de répondre. 
        Ne réponds JAMAIS sans avoir vérifié les données !

        🗓️ CONTEXTE TEMPOREL ACTUEL:
        - Nous sommes le : {aujourd_hui.strftime('%A %d %B %Y')} ({aujourd_hui.isoformat()})
        - Il est actuellement : {maintenant.strftime('%H:%M')}
        - Demain sera : {demain.strftime('%A %d %B %Y')} ({demain.isoformat()})
        - Cette semaine : du {debut_semaine.strftime('%A %d %B')} au {fin_semaine.strftime('%A %d %B %Y')}
        - Semaine prochaine : du {debut_semaine_prochaine.strftime('%A %d %B')} au {fin_semaine_prochaine.strftime('%A %d %B %Y')}

        📅 RÉFÉRENCES TEMPORELLES:
        - "aujourd'hui" = {aujourd_hui.isoformat()}
        - "demain" = {demain.isoformat()}
        - "cette semaine" = {debut_semaine.isoformat()} à {fin_semaine.isoformat()}
        - "la semaine prochaine" = {debut_semaine_prochaine.isoformat()} à {fin_semaine_prochaine.isoformat()}
        - "lundi prochain" = {(debut_semaine_prochaine).isoformat()}
        - "ce weekend" = {(fin_semaine - timedelta(days=1)).isoformat()} à {fin_semaine.isoformat()}

        🔧 FONCTIONS OBLIGATOIRES :
        - Pour "mes cours demain/aujourd'hui/cette semaine" → UTILISE get_courses_by_date_range()
        - Pour "mes cours de maths/français" → UTILISE get_courses_by_subject()  
        - Pour "suis-je libre" → UTILISE get_free_time_slots()
        - Pour "mon prochain cours" → UTILISE get_next_course()

        RÈGLES IMPORTANTES:
        1. ⚠️ APPELLE TOUJOURS les fonctions avant de répondre. Ne fais JAMAIS d'hypothèses sur les données !
        2. Quand tu proposes des sessions de révision ET que l'utilisateur accepte (dit "oui", "d'accord", "merci", "ajoute-les"), 
           tu DOIS utiliser add_event_to_calendar pour CHAQUE session.
        3. Format des dates pour les fonctions: "YYYY-MM-DDTHH:MM:SS" (ex: "2025-01-15T08:00:00")
        4. Détecte les confirmations: "oui", "merci", "d'accord", "parfait", "génial" = AJOUT AUTOMATIQUE
        5. IMPORTANT: Ne passe PAS le paramètre user_id dans tes function calls - il est automatiquement fourni.
        """
        
        messages = [{"role": "system", "content": system_message}]
        
        # Ajouter l'historique des messages
        if "messages" in st.session_state and len(st.session_state.messages) > 0:
            recent_messages = st.session_state.messages[-4:]
            for msg in recent_messages:
                messages.append({"role": msg["role"], "content": msg["content"]})
        
        messages.append({"role": "user", "content": prompt})
        
        logger.info(f"📨 Messages envoyés à OpenAI: {len(messages)}")
        logger.info(f"🔧 Outils envoyés: {[tool['function']['name'] for tool in TOOLS]}")
        
        # Détecter si on doit forcer un appel de fonction
        force_tool = None
        if "cours" in prompt.lower():
            if any(word in prompt.lower() for word in ["demain", "aujourd'hui", "cette semaine", "semaine prochaine"]):
                force_tool = {"type": "function", "function": {"name": "get_courses_by_date_range"}}
                logger.info("🎯 Forçage d'appel de fonction: get_courses_by_date_range")
            elif any(subject in prompt.lower() for subject in ["math", "français", "anglais", "physique", "chimie", "histoire", "géo"]):
                force_tool = {"type": "function", "function": {"name": "get_courses_by_subject"}}
                logger.info("🎯 Forçage d'appel de fonction: get_courses_by_subject")
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice=force_tool if force_tool else "auto",
            temperature=0.7,
            max_tokens=2000
        )
        
        message = response.choices[0].message
        logger.info(f"🤖 Réponse OpenAI reçue")
        logger.info(f"📝 Contenu: {message.content if message.content else 'Aucun contenu'}")
        logger.info(f"🔧 Tool calls: {len(message.tool_calls) if message.tool_calls else 0}")
        
        # Vérifier si l'IA veut utiliser des outils
        if hasattr(message, 'tool_calls') and message.tool_calls:
            logger.info(f"🔧 L'IA veut utiliser {len(message.tool_calls)} outil(s)")
            
            messages.append(message)
            
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"📞 Appel fonction: {function_name}")
                logger.info(f"📝 Arguments bruts: {function_args}")
                
                # Supprimer user_id des arguments si présent  
                if 'user_id' in function_args:
                    del function_args['user_id']
                    logger.info(f"🔧 user_id supprimé des arguments")
                
                logger.info(f"📝 Arguments finaux: {function_args}")
                
                if function_name in AVAILABLE_FUNCTIONS:
                    try:
                        # user_id est passé explicitement comme premier paramètre
                        function_result = AVAILABLE_FUNCTIONS[function_name](user_id, **function_args)
                        
                        logger.info(f"✅ Résultat fonction: {function_result}")
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",  
                            "name": function_name,
                            "content": json.dumps(function_result, ensure_ascii=False)
                        })
                    except Exception as func_error:
                        logger.error(f"❌ Erreur lors de l'appel de {function_name}: {func_error}")
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",  
                            "name": function_name,
                            "content": json.dumps({"error": str(func_error)}, ensure_ascii=False)
                        })
                else:
                    logger.error(f"❌ Fonction inconnue: {function_name}")
            
            logger.info("🔄 Génération de la réponse finale...")
            final_response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            final_content = final_response.choices[0].message.content
            logger.info(f"✅ Réponse finale générée: {final_content[:100]}...")
            return final_content
        else:
            logger.warning("⚠️ L'IA n'a fait aucun appel de fonction !")
            logger.warning(f"📝 Réponse directe: {message.content}")
            
        return message.content
        
    except Exception as e:
        logger.error(f"❌ Erreur génération réponse: {e}")
        import traceback
        logger.error(f"📍 Traceback: {traceback.format_exc()}")
        return f"❌ Désolé, une erreur est survenue: {str(e)}"





def main():
    st.set_page_config(page_title="Planning Assistant", layout="wide")
    
    check_api_key()
    
    # Initialiser l'historique des messages
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📅 Votre emploi du temps")
        
        # Zone de saisie simple
        user_id = st.text_input(
            "Entrez votre identifiant :",
            placeholder="ex: htiaiba, jdupont, marie.martin...",
            help="Votre identifiant pour récupérer l'emploi du temps"
        )
        
        # Affichage du calendrier seulement si un identifiant est saisi
        if user_id:
            user_id = user_id.strip().lower()
            
            # Boutons d'action
            refresh_col1, refresh_col2 = st.columns([1, 1])
            with refresh_col1:
                if st.button("🔄 Rafraîchir l'emploi du temps"):
                    with st.spinner("Mise à jour en cours..."):
                        get_edt_semaine_json(user_id)
                    st.rerun()
            
            with refresh_col2:
                if st.button("🧹 Supprimer les évènements AI"):
                    from schedule_functions import remove_revision_events
                    result = remove_revision_events(user_id)
                    st.info(result["message"])
                    st.rerun()
            
            # S'assurer que les données existent
            if ensure_schedule_data(user_id):
                schedule_data = load_schedule_data(user_id)
                
                if schedule_data:
                    # Configuration du calendrier
                    calendar_options = {
                        "editable": False,
                        "selectable": True,
                        "locale": "fr",
                        "firstDay": 1,
                        "headerToolbar": {
                            "left": "prev,next today",
                            "center": "title",
                            "right": "dayGridMonth,timeGridWeek,timeGridDay"
                        },
                        "buttonText": {
                            "today": "Aujourd'hui",
                            "month": "Mois", 
                            "week": "Semaine",
                            "day": "Jour"
                        },
                        "initialView": "timeGridWeek",
                        "height": 650,
                        "slotMinTime": "07:00:00",
                        "slotMaxTime": "19:00:00",
                        "allDaySlot": False,
                        "weekends": True,
                        "nowIndicator": True,
                        "eventDisplay": "block",
                        "displayEventTime": True,
                        "eventTimeFormat": {
                            "hour": "2-digit",
                            "minute": "2-digit", 
                            "meridiem": False
                        }
                    }
                    
                    calendar_result = calendar(
                        events=schedule_data,
                        options=calendar_options,
                        custom_css=custom_css_outside
                    )
                    
                    # Statistiques
                    total_events = len(schedule_data)
                    ai_events = len([e for e in schedule_data if e.get("extendedProps", {}).get("added_by_ai")])
                    
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Total événements", total_events)
                    with col_stat2:
                        st.metric("Cours", total_events - ai_events) 
                    with col_stat3:
                        st.metric("Évènements ajoutés", ai_events, delta=ai_events if ai_events > 0 else None)
                else:
                    st.error("❌ Aucun cours trouvé")
        else:
            st.info("👆 Entrez votre identifiant pour voir votre emploi du temps et commencer la discution")
    
    with col2:
        st.subheader("🤖 Assistant de révisions")
        
        # Chat seulement si identifiant saisi
        if user_id:
            st.markdown("### 💬 Conversation")
            
            messages_container = st.container(height=500, border=True)
            with messages_container:
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
            
            if prompt := st.chat_input("Que voulez-vous réviser ?"):
                st.session_state.messages.append({"role": "user", "content": prompt})

                with st.spinner("🤔 Analyse en cours..."):
                    # 🎯 Plus besoin de liste_dates ! L'IA les détermine automatiquement
                    response = generate_response(prompt, user_id=user_id)

                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
        else:
            st.info("La discution s'affichera ici")


custom_css_outside = """
/* Thème sombre moderne */
.fc {
    background-color: #2d3748 !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* En-têtes */
.fc-toolbar {
    background-color: #1a202c !important;
    border-radius: 12px !important;
    padding: 15px !important;
    margin-bottom: 15px !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
}

.fc-toolbar-title {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}

/* Boutons */
.fc-button {
    background-color: #4a5568 !important;
    border: 1px solid #4a5568 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.fc-button:hover {
    background-color: #2b6cb0 !important;
    border-color: #2b6cb0 !important;
    transform: translateY(-1px) !important;
}

.fc-button-active {
    background-color: #3182ce !important;
    border-color: #3182ce !important;
}

/* Grille du calendrier - CORRECTION ICI */
.fc-theme-standard th,
.fc-theme-standard td {
    border-color: #4a5568 !important;
    background-color: #2d3748 !important;
}

/* En-têtes des jours */
.fc-col-header {
    background-color: #1a202c !important;
}

.fc-col-header-cell {
    background-color: #1a202c !important;
    color: #cbd5e0 !important;
    font-weight: 600 !important;
    padding: 12px 5px !important;
}

/* Colonne des heures */
.fc-timegrid-slot-label {
    color: #a0aec0 !important;
    font-weight: 500 !important;
}

.fc-timegrid-axis {
    background-color: #1a202c !important;
}

/* Lignes d'heures */
.fc-timegrid-slot {
    border-color: #4a5568 !important;
}

.fc-timegrid-slot-minor {
    border-color: #2d3748 !important;
}

/* CORRECTION PRINCIPALE - Jour actuel */
.fc-day-today {
    background-color: #2d3748 !important;  /* Fond sombre au lieu de blanc */
    position: relative !important;
}

/* Ajouter une bordure colorée pour indiquer le jour actuel */
.fc-day-today::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 3px !important;
    background: linear-gradient(90deg, #3b82f6, #06b6d4) !important;
    z-index: 1 !important;
}

/* En-tête du jour actuel */
.fc-day-today .fc-col-header-cell {
    background-color: #3b82f6 !important;
    color: white !important;
    font-weight: 700 !important;
}

/* Cellules de temps pour le jour actuel */
.fc-day-today .fc-timegrid-col {
    background-color: rgba(59, 130, 246, 0.05) !important;  /* Très léger bleu */
}

/* Événements/Cours */
.fc-event {
    border-radius: 8px !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 2px 6px !important;
}

.fc-event-time {
    font-weight: 700 !important;
    font-size: 0.8rem !important;
}

.fc-event-title {
    font-weight: 600 !important;
}

/* Indicateur de temps actuel */
.fc-timegrid-now-indicator-line {
    border-color: #ef4444 !important;
    border-width: 2px !important;
}

.fc-timegrid-now-indicator-arrow {
    border-left-color: #ef4444 !important;
    border-right-color: #ef4444 !important;
}

/* Animations */
.fc-event:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.2s ease !important;
}

/* Responsive */
@media (max-width: 768px) {
    .fc-toolbar {
        flex-direction: column !important;
        gap: 10px !important;
    }
    
    .fc-toolbar-title {
        font-size: 1.2rem !important;
    }
    
    .fc-button {
        padding: 6px 10px !important;
        font-size: 0.85rem !important;
    }
}
"""


if __name__ == "__main__":
    main()
