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
    """Récupère les cours dans une plage de dates donnée avec correction timezone."""
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
        
        # === EXTRACTION ÉVÉNEMENTS (Compatible avec ta structure) ===
        all_events = []
        if isinstance(data, dict) and "emploi_du_temps" in data:
            logger.info(f"📊 Structure emploi_du_temps détectée")
            for semaine_data in data["emploi_du_temps"]:
                all_events.extend(semaine_data.get("evenements", []))
        elif isinstance(data, list):
            logger.info(f"📊 Structure liste détectée")
            all_events = data
        
        logger.info(f"📊 {len(all_events)} événements extraits")
        
        # === PARSING DATES DE RECHERCHE ===
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # 🎯 CORRECTION CRUCIALE : Si end_date est à 00:00:00, la mettre à 23:59:59
        if end_dt.time() == datetime.min.time():
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            logger.info(f"🔧 Date fin corrigée: {end_dt}")
        
        logger.info(f"📅 Période finale: {start_dt} → {end_dt}")
        
        # === FILTRAGE AVEC GESTION DES DEUX FORMATS ===
        filtered_courses = []
        
        for event in all_events:
            try:
                # 🎯 Gérer les deux formats de dates possibles
                debut_field = event.get("début") or event.get("start", "")
                if not debut_field:
                    continue
                
                # Parse la date (compatible avec le format de ton scraper: 'YYYY-MM-DD HH:MM')
                if "T" in debut_field:
                    course_start = datetime.fromisoformat(debut_field.replace('T', ' ').split('+')[0])
                else:
                    course_start = datetime.strptime(debut_field, "%Y-%m-%d %H:%M")
                
                # Test de la période
                is_in_range = start_dt <= course_start <= end_dt
                logger.info(f"📅 {event.get('nom_cours', event.get('title', 'Cours'))}: {course_start} dans [{start_dt} - {end_dt}] = {is_in_range}")
                
                if is_in_range:
                    # Récupérer le nom du cours selon le format
                    nom_cours = event.get('nom_cours') or event.get('title', 'Cours sans nom')
                    
                    # Exclure les révisions et événements non-cours
                    if not (nom_cours.startswith('Révision') or 
                            nom_cours.startswith('VACANCES') or 
                            nom_cours.startswith('Férié')):
                        
                        # Gérer fin de cours
                        fin_field = event.get('fin') or event.get('end', '')
                        if fin_field and "T" in fin_field:
                            fin_field = fin_field.replace('T', ' ').split('+')[0]
                        
                        filtered_courses.append({
                            'title': nom_cours,
                            'start': course_start.isoformat(),
                            'end': fin_field,
                            'professeur': event.get('professeur', ''),
                            'location': event.get('location', ''),
                            'description': event.get('description', '')
                        })
                        logger.info(f"✅ COURS AJOUTÉ: {nom_cours} à {course_start}")
                        
            except Exception as e:
                logger.error(f"❌ Erreur traitement événement: {e}")
                continue
        
        logger.info(f"🎯 RÉSULTAT FINAL: {len(filtered_courses)} cours trouvé(s)")
        
        return {
            'status': 'success',
            'period': f"{start_date} à {end_date}",
            'courses': filtered_courses,
            'count': len(filtered_courses)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_courses_by_date_range: {e}")
        import traceback
        logger.error(f"📍 Traceback: {traceback.format_exc()}")
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
    """Version améliorée du prochain cours avec plus de détails."""
    try:
        logger.info(f"🔍 Recherche prochain cours pour {user_id}")
        
        data = load_schedule_data(user_id)
        if not data:
            return {
                "status": "error",
                "message": "❌ Aucun emploi du temps trouvé"
            }
        
        # Extraction des événements selon la structure
        all_events = []
        if isinstance(data, dict) and "emploi_du_temps" in data:
            for semaine_data in data["emploi_du_temps"]:
                all_events.extend(semaine_data.get("evenements", []))
        elif isinstance(data, list):
            all_events = data
        
        # Filtrage des cours futurs
        now = datetime.now()
        upcoming_courses = []
        
        for event in all_events:
            try:
                debut_field = event.get("début") or event.get("start", "")
                if not debut_field:
                    continue
                
                # Parse date flexible
                if "T" in debut_field:
                    course_start = datetime.fromisoformat(debut_field.replace('T', ' ').split('+')[0])
                else:
                    course_start = datetime.strptime(debut_field, "%Y-%m-%d %H:%M")
                
                if course_start > now:
                    nom_cours = event.get('nom_cours') or event.get('title', 'Cours')
                    
                    # Exclure les non-cours
                    if not any(exclude in nom_cours for exclude in 
                              ['Révision', 'VACANCES', 'Férié', 'révision']):
                        
                        upcoming_courses.append({
                            "title": nom_cours,
                            "start_datetime": course_start,
                            "start": debut_field,
                            "end": event.get('fin') or event.get('end', ''),
                            "professeur": event.get('professeur', 'Inconnu'),
                            "location": event.get('location', ''),
                            "description": event.get('description', '')
                        })
                        
            except Exception as e:
                logger.warning(f"⚠️ Erreur traitement cours futur: {e}")
                continue
        
        if not upcoming_courses:
            return {
                "status": "info",
                "message": "📅 Aucun cours à venir dans votre emploi du temps",
                "next_course": None
            }
        
        # Trier et prendre le plus proche
        upcoming_courses.sort(key=lambda x: x["start_datetime"])
        next_course = upcoming_courses[0]
        
        # Calcul du temps restant amélioré
        time_until = next_course["start_datetime"] - now
        days = time_until.days
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Formatage du temps
        if days > 0:
            time_str = f"{days} jour{'s' if days > 1 else ''} et {hours}h{minutes:02d}min"
        elif hours > 0:
            time_str = f"{hours}h{minutes:02d}min"
        else:
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''}"
        
        next_course["time_until"] = time_str
        next_course["is_today"] = next_course["start_datetime"].date() == now.date()
        next_course["is_tomorrow"] = (next_course["start_datetime"].date() - now.date()).days == 1
        
        # Ajouter les cours suivants (optionnel)
        next_course["following_courses"] = [
            {
                "title": course["title"],
                "start": course["start"],
                "professeur": course["professeur"]
            }
            for course in upcoming_courses[1:4]  # 3 cours suivants
        ]
        
        logger.info(f"✅ Prochain cours: {next_course['title']} dans {time_str}")
        
        return {
            "status": "success",
            "next_course": next_course,
            "total_upcoming": len(upcoming_courses)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_next_course: {str(e)}")
        return {
            "status": "error",
            "message": f"❌ Erreur lors de la recherche: {str(e)}"
        }


def add_event_to_calendar(user_id: str, title: str, start_date: str, end_date: str, description: str = "") -> dict:
    """Version améliorée avec validation et structure flexible."""
    try:
        logger.info(f"🎯 AJOUT ÉVÉNEMENT: {title} pour {user_id}")
        
        # Validation des dates
        try:
            start_dt = datetime.fromisoformat(start_date.replace('T', ' ').split('+')[0])
            end_dt = datetime.fromisoformat(end_date.replace('T', ' ').split('+')[0])
            
            if start_dt >= end_dt:
                return {"success": False, "message": "❌ Date de fin doit être après la date de début"}
                
        except ValueError as e:
            return {"success": False, "message": f"❌ Format de date invalide: {str(e)}"}
        
        # Validation du titre
        if not title.strip():
            return {"success": False, "message": "❌ Le titre ne peut pas être vide"}
        
        json_dir = "json_schedules"
        os.makedirs(json_dir, exist_ok=True)
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        # Charger structure existante
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"emploi_du_temps": [], "revisions": []}
        
        # Créer l'événement
        nouveau_event = {
            "nom_cours": title,
            "début": start_dt.strftime('%Y-%m-%d %H:%M'),
            "fin": end_dt.strftime('%Y-%m-%d %H:%M'),
            "description": description,
            "professeur": "IA Assistant",
            "location": "",
            "extendedProps": {
                "type": "revision",
                "added_by_ai": True,
                "created_at": datetime.now().isoformat(),
                "color": "#10b981",
                "textColor": "#ffffff"
            }
        }
        
        # Ajout selon la structure
        total_events = 0
        if isinstance(data, list):
            data.append(nouveau_event)
            total_events = len(data)
        elif isinstance(data, dict):
            if "revisions" not in data:
                data["revisions"] = []
            data["revisions"].append(nouveau_event)
            total_events = len(data["revisions"])
        
        # Sauvegarde avec backup
        backup_file = f"{json_file}.backup"
        if os.path.exists(json_file):
            import shutil
            shutil.copy2(json_file, backup_file)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Événement ajouté! Total: {total_events}")
        
        return {
            "success": True,
            "message": f"✅ '{title}' ajouté avec succès pour le {start_dt.strftime('%d/%m/%Y à %H:%M')}",
            "event": nouveau_event,
            "total_events": total_events,
            "date_added": datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur ajout événement: {str(e)}")
        return {
            "success": False, 
            "message": f"❌ Erreur lors de l'ajout: {str(e)}"
        }


def remove_revision_events(user_id: str) -> dict:
    """Version améliorée avec statistiques détaillées."""
    try:
        logger.info(f"🗑️ SUPPRESSION révisions pour {user_id}")
        
        json_dir = "json_schedules"
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        if not os.path.exists(json_file):
            return {
                "success": False, 
                "message": "❌ Aucun fichier emploi du temps trouvé"
            }
        
        # Backup avant suppression
        backup_file = f"{json_file}.backup"
        import shutil
        shutil.copy2(json_file, backup_file)
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        removed_events = []
        
        if isinstance(data, list):
            # Structure liste
            original_count = len(data)
            removed_events = [event for event in data 
                            if event.get("extendedProps", {}).get("added_by_ai", False)]
            data[:] = [event for event in data 
                        if not event.get("extendedProps", {}).get("added_by_ai", False)]
            removed_count = original_count - len(data)
            
        elif isinstance(data, dict):
            # Structure objet
            if "revisions" in data:
                removed_events = data["revisions"].copy()
                removed_count = len(removed_events)
                data["revisions"] = []
        
        # Sauvegarder
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Statistiques
        if removed_events:
            event_titles = [event.get('nom_cours', event.get('title', 'Sans titre')) 
                            for event in removed_events[:3]]
            detail_msg = f"Supprimé: {', '.join(event_titles)}"
            if len(removed_events) > 3:
                detail_msg += f" (+{len(removed_events)-3} autres)"
        else:
            detail_msg = "Aucune révision à supprimer"
        
        logger.info(f"✅ {removed_count} révisions supprimées")
        
        return {
            "success": True,
            "message": f"✅ {removed_count} révision{'s' if removed_count > 1 else ''} supprimée{'s' if removed_count > 1 else ''}",
            "removed_count": removed_count,
            "details": detail_msg,
            "backup_created": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur suppression: {str(e)}")
        return {
            "success": False, 
            "message": f"❌ Erreur lors de la suppression: {str(e)}"
        }


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
