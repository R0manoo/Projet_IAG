import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
logger = logging.getLogger(__name__)

def load_schedule_data(user_id: str) -> List[Dict[str, Any]]:
    """
    Charge les données d'emploi du temps avec gestion des structures corrompues.
    """
    json_dir = "json_schedules"
    json_file = os.path.join(json_dir, f"{user_id}_edt.json")
    
    if not os.path.exists(json_file):
        logger.info(f"❌ Fichier non trouvé: {json_file}")
        return []
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        all_events = []
        
        # 🎯 CAS 1: Structure correcte (objet avec emploi_du_temps)
        if isinstance(data, dict) and "emploi_du_temps" in data:
            # Charger les cours
            for semaine_data in data["emploi_du_temps"]:
                for event in semaine_data.get("evenements", []):
                    formatted_event = {
                        "title": event.get("nom_cours", "Cours"),
                        "start": event.get("début", ""),
                        "end": event.get("fin", ""),
                        "professeur": event.get("professeur", ""),
                        "color": get_color_for_course(event.get("nom_cours", ""))
                    }
                    all_events.append(formatted_event)
            
            # Ajouter les révisions si elles existent
            revisions = data.get("revisions", [])
            all_events.extend(revisions)
            
        # 🎯 CAS 2: Liste directe (structure aplatie/corrompue)
        elif isinstance(data, list):
            logger.info(f"📋 Structure liste détectée, chargement direct...")
            all_events = data  # Directement la liste
            
        else:
            logger.error(f"❌ Structure non reconnue: {type(data)}")
            return []
        
        logger.info(f"✅ {len(all_events)} événement(s) chargé(s) pour {user_id}")
        return all_events
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement: {str(e)}")
        return []


def get_color_for_course(course_name: str) -> str:
    """Attribue une couleur basée sur le nom du cours"""
    colors = {
        "Mathématiques": "#ff6b6b",
        "Informatique": "#4ecdc4", 
        "Physique": "#45b7d1",
        "Chimie": "#96ceb4",
        "Anglais": "#feca57",
        "Histoire": "#ff9ff3",
        "Géographie": "#54a0ff"
    }
    
    # Recherche par mots-clés
    course_lower = course_name.lower()
    for subject, color in colors.items():
        if subject.lower() in course_lower:
            return color
    
    # Couleur par défaut
    return "#3788d8"

def get_courses_by_date_range(user_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Récupère les cours dans une plage de dates donnée."""
    try:
        logger.info(f"🔥 === DÉBUT GET_COURSES_BY_DATE_RANGE ===")
        logger.info(f"📅 Dates reçues: {start_date} → {end_date}")
        
        # === CHARGEMENT FICHIER ===
        json_dir = "json_schedules"
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        if not os.path.exists(json_file):
            return {'status': 'error', 'message': 'Fichier emploi du temps non trouvé'}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # === EXTRACTION ÉVÉNEMENTS ===
        all_events = []
        if isinstance(data, dict) and "emploi_du_temps" in data:
            for semaine_data in data["emploi_du_temps"]:
                all_events.extend(semaine_data.get("evenements", []))
        
        # === CORRECTION DES DATES ===
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # 🎯 CORRECTION : Si end_date est à 00:00:00, la mettre à 23:59:59
        if end_dt.time() == datetime.min.time():
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            logger.info(f"🔧 Date fin corrigée: {end_dt}")
        
        logger.info(f"📅 Période de recherche: {start_dt} → {end_dt}")
        
        # === FILTRAGE ===
        filtered_courses = []
        
        for event in all_events:
            try:
                course_start_str = event.get("début", "")
                if not course_start_str:
                    continue
                    
                course_start = datetime.strptime(course_start_str, "%Y-%m-%d %H:%M")
                
                # Test de la période
                is_in_range = start_dt <= course_start <= end_dt
                
                if is_in_range:
                    nom_cours = event.get('nom_cours', '')
                    # Exclure les révisions et événements non-cours
                    if not (nom_cours.startswith('Révision') or 
                            nom_cours.startswith('VACANCES') or 
                            nom_cours.startswith('Férié')):
                        
                        filtered_courses.append({
                            'title': nom_cours,
                            'start': course_start.isoformat(),
                            'end': event.get('fin', ''),
                            'professeur': event.get('professeur', ''),
                            'location': event.get('location', ''),
                            'description': event.get('description', '')
                        })
                        logger.info(f"✅ COURS AJOUTÉ: {nom_cours} à {course_start}")
                        
            except Exception as e:
                continue
        
        logger.info(f"🎯 RÉSULTAT: {len(filtered_courses)} cours trouvé(s)")
        
        return {
            'status': 'success',
            'period': f"{start_date} à {end_date}",
            'courses': filtered_courses,
            'count': len(filtered_courses)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return {'status': 'error', 'message': str(e)}


def get_courses_by_subject(user_id: str, subject: str) -> Dict[str, Any]:
    """Récupère les cours d'une matière spécifique."""
    try:
        schedule_data = load_schedule_data(user_id)
        
        if not schedule_data:
            return {'status': 'success', 'courses': [], 'count': 0}
        
        filtered_courses = []
        subject_lower = subject.lower()
        
        for course in schedule_data:
            # 🎯 CORRECTION : Gérer les deux formats
            course_name = (course.get("title") or course.get("nom_cours", "")).lower()
            
            if subject_lower in course_name:
                filtered_courses.append({
                    'title': course.get('title') or course.get('nom_cours', 'Sans titre'),
                    'start': course.get('start') or course.get('début', ''),
                    'end': course.get('end') or course.get('fin', ''),
                    'professeur': course.get('professeur', ''),
                })
        
        return {
            'status': 'success',
            'subject': subject,
            'courses': filtered_courses,
            'count': len(filtered_courses)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_courses_by_subject: {e}")
        return {'status': 'error', 'message': str(e)}


def get_free_time_slots(user_id: str, date: str) -> List[Dict[str, str]]:
    """
    Trouve les créneaux libres dans une journée donnée.
    """
    schedule_data = load_schedule_data(user_id)
    if not schedule_data:
        return []
    
    # Filtrer les cours du jour demandé
    target_date = datetime.fromisoformat(date).date()
    day_courses = []
    
    for course in schedule_data:
        try:
            course_date = datetime.strptime(course["début"], "%Y-%m-%d %H:%M").date()
            if course_date == target_date:
                day_courses.append({
                    "start": datetime.strptime(course["début"], "%Y-%m-%d %H:%M").time(),
                    "end": datetime.strptime(course["fin"], "%Y-%m-%d %H:%M").time(),
                    "title": course["nom_cours"]
                })
        except (ValueError, KeyError):
            continue
    
    # Trier par heure de début
    day_courses.sort(key=lambda x: x["start"])
    
    # Trouver les créneaux libres
    free_slots = []
    day_start = datetime.strptime("08:00", "%H:%M").time()
    day_end = datetime.strptime("18:00", "%H:%M").time()
    
    if not day_courses:
        return [{
            "start": "08:00",
            "end": "18:00", 
            "description": "Toute la journée libre"
        }]
    
    # Créneau libre avant le premier cours
    if day_courses[0]["start"] > day_start:
        free_slots.append({
            "start": day_start.strftime("%H:%M"),
            "end": day_courses[0]["start"].strftime("%H:%M"),
            "description": f"Libre avant {day_courses[0]['title']}"
        })
    
    # Créneaux libres entre les cours
    for i in range(len(day_courses) - 1):
        current_end = day_courses[i]["end"]
        next_start = day_courses[i + 1]["start"]
        
        if current_end < next_start:
            free_slots.append({
                "start": current_end.strftime("%H:%M"),
                "end": next_start.strftime("%H:%M"),
                "description": f"Libre entre {day_courses[i]['title']} et {day_courses[i+1]['title']}"
            })
    
    # Créneau libre après le dernier cours
    if day_courses[-1]["end"] < day_end:
        free_slots.append({
            "start": day_courses[-1]["end"].strftime("%H:%M"),
            "end": day_end.strftime("%H:%M"),
            "description": f"Libre après {day_courses[-1]['title']}"
        })
    
    return free_slots

def get_next_course(user_id: str) -> Dict[str, Any]:
    """
    Récupère le prochain cours à venir.
    """
    schedule_data = load_schedule_data(user_id)
    if not schedule_data:
        return {}
    
    now = datetime.now()
    upcoming_courses = []
    
    for course in schedule_data:
        try:
            course_start = datetime.strptime(course["début"], "%Y-%m-%d %H:%M")
            if course_start > now:
                upcoming_courses.append({
                    **course,
                    "start_datetime": course_start
                })
        except (ValueError, KeyError):
            continue
    
    if not upcoming_courses:
        return {}
    
    # Trier par date de début et prendre le premier
    upcoming_courses.sort(key=lambda x: x["start_datetime"])
    next_course = upcoming_courses[0]
    
    # Calculer le temps restant
    time_until = next_course["start_datetime"] - now
    days = time_until.days
    hours, remainder = divmod(time_until.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    next_course["time_until"] = f"{days} jours, {hours}h {minutes}min"
    
    return next_course
def add_event_to_calendar(user_id: str, title: str, start_date: str, end_date: str, description: str = "") -> dict:
    """Ajoute un événement sans corrompre la structure"""
    from datetime import datetime
    
    logger.info(f"🎯 TENTATIVE AJOUT: {title} pour {user_id}")
    
    try:
        json_dir = "json_schedules"
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        # Charger la structure actuelle
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        
        # Créer l'événement de révision
        nouveau_event = {
            "title": title,
            "start": start_date,
            "end": end_date,
            "description": description,
            "color": "#10b981",
            "textColor": "#ffffff",
            "borderColor": "#059669",
            "extendedProps": {
                "type": "revision",
                "added_by_ai": True,
                "created_at": datetime.now().isoformat()
            }
        }
        
        # 🎯 AJOUT SELON LA STRUCTURE
        if isinstance(data, list):
            # Structure liste : ajouter directement
            data.append(nouveau_event)
            total_events = len(data)
        else:
            # Structure objet : ajouter aux révisions
            if "revisions" not in data:
                data["revisions"] = []
            data["revisions"].append(nouveau_event)
            total_events = len(data.get("revisions", []))
        
        # Sauvegarder
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Révision ajoutée ! Total: {total_events}")
        
        return {
            "success": True,
            "message": f"✅ Session '{title}' ajoutée avec succès !",
            "event": nouveau_event,
            "total_events": total_events
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur ajout: {str(e)}")
        return {"success": False, "message": f"❌ Erreur: {str(e)}"}



def remove_revision_events(user_id: str) -> dict:
    """Supprime les révisions selon la structure du fichier"""
    try:
        json_dir = "json_schedules"
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        if not os.path.exists(json_file):
            return {"success": False, "message": "❌ Aucun fichier trouvé"}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        
        if isinstance(data, list):
            # Structure liste : filtrer les révisions AI
            original_count = len(data)
            data = [event for event in data 
                    if not (event.get("extendedProps", {}).get("added_by_ai", False))]
            removed_count = original_count - len(data)
            
        elif isinstance(data, dict):
            # Structure objet : vider les révisions
            removed_count = len(data.get("revisions", []))
            data["revisions"] = []
        
        # Sauvegarder
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"✅ {removed_count} révision(s) supprimée(s)"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur suppression: {str(e)}")
        return {"success": False, "message": f"❌ Erreur: {str(e)}"}



AVAILABLE_FUNCTIONS = {
    "get_courses_by_date_range": get_courses_by_date_range,
    "get_courses_by_subject": get_courses_by_subject, 
    "get_free_time_slots": get_free_time_slots,
    "get_next_course": get_next_course,
    "add_event_to_calendar": add_event_to_calendar,  
    "remove_revision_events": remove_revision_events  
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_courses_by_date_range",
            "description": "Récupère les cours dans une plage de dates donnée",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "format": "date", "description": "Date de début (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "format": "date", "description": "Date de fin (YYYY-MM-DD)"}
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_courses_by_subject",
            "description": "Récupère les cours d'une matière spécifique",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "La matière recherchée"}
                },
                "required": ["subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_free_time_slots",
            "description": "Trouve les créneaux libres dans une journée donnée",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date", "description": "La date à analyser (YYYY-MM-DD)"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_next_course",
            "description": "Récupère le prochain cours à venir",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_event_to_calendar",
            "description": "Ajoute une session de révision au calendrier de l'utilisateur",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre de la session (ex: 'Révision Mathématiques')"},
                    "start_date": {"type": "string", "description": "Date et heure de début (format: 2024-06-03T08:00:00)"},
                    "end_date": {"type": "string", "description": "Date et heure de fin (format: 2024-06-03T09:30:00)"},
                    "description": {"type": "string", "description": "Description optionnelle de la session"}
                },
                "required": ["title", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "remove_revision_events",
            "description": "Supprime toutes les sessions de révision ajoutées par l'IA",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
