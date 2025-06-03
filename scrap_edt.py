from collections import defaultdict
import os
import openai
import requests
from ics import Calendar
import pytz
from dotenv import load_dotenv
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

# Configuration du logger
logger = logging.getLogger(__name__)

def get_edt(user_id: str) -> List[Dict[str, str]]:
    """Récupère l'emploi du temps complet avec gestion d'erreurs améliorée."""
    try:
        logger.info(f"🔄 Récupération EDT pour {user_id}")
        
        ics_url = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
        
        # Requête avec timeout et retry
        response = requests.get(ics_url, timeout=30)
        response.encoding = "UTF-8"
        
        if not response.ok:
            logger.error(f"❌ Erreur HTTP {response.status_code} pour {user_id}")
            raise Exception(f"Identifiant invalide ou serveur inaccessible (Code: {response.status_code}) 🚫")

        cal = Calendar(response.text)
        cours = []
        local_tz = pytz.timezone("Pacific/Noumea")
        
        logger.info(f"📅 Traitement de {len(cal.events)} événements")

        for i, event in enumerate(cal.events):
            try:
                # Conversion timezone sécurisée
                start_local = event.begin.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')
                end_local = event.end.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')

                # Nettoyage des noms
                nom_coupee = (event.name or "Cours sans nom").split('(')[0].strip()
                description_coupee = (event.description or "").split('(')[0].strip()
                
                # Extraction du professeur depuis la description
                professeur = "Inconnu"
                if event.description and '\n' in event.description:
                    lines = event.description.split('\n')
                    for line in lines:
                        if any(keyword in line.lower() for keyword in ['prof', 'enseignant', 'teacher']):
                            professeur = line.strip()
                            break

                cours.append({
                    "nom_cours": nom_coupee,
                    "début": start_local,
                    "fin": end_local,
                    "description": description_coupee,
                    "professeur": professeur,
                    "location": getattr(event, 'location', '') or ''
                })
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur traitement événement {i+1}: {e}")
                continue

        logger.info(f"✅ {len(cours)} cours récupérés pour {user_id}")
        return cours
        
    except requests.exceptions.Timeout:
        raise Exception("⏰ Timeout : Le serveur met trop de temps à répondre")
    except requests.exceptions.RequestException as e:
        raise Exception(f"🌐 Erreur réseau : {str(e)}")
    except Exception as e:
        logger.error(f"❌ Erreur get_edt: {str(e)}")
        raise

def get_edt_semaine(user_id: str) -> Dict[str, Any]:
    """Version améliorée avec structure organisée par semaine et sauvegarde automatique."""
    try:
        logger.info(f"🗓️ Récupération EDT par semaine pour {user_id}")
        
        ics_url = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
        response = requests.get(ics_url, timeout=30)
        response.encoding = "UTF-8"
        
        if not response.ok:
            raise Exception(f"Identifiant invalide ou serveur inaccessible (Code: {response.status_code}) 🚫")

        cal = Calendar(response.text)
        cours_par_semaine = defaultdict(list)
        local_tz = pytz.timezone("Pacific/Noumea")
        
        stats = {"total_events": 0, "processed": 0, "errors": 0}

        logger.info(f"📅 Traitement de {len(cal.events)} événements")

        for event in cal.events:
            try:
                stats["total_events"] += 1
                
                start_local = event.begin.astimezone(local_tz)
                end_local = event.end.astimezone(local_tz)
                week_num = start_local.isocalendar()[1]
                
                nom_coupee = (event.name or "Cours sans nom").split('(')[0].strip()
                description_coupee = (event.description or "").split('(')[0].strip()
                
                # Extraction professeur améliorée
                professeur = "Inconnu"
                if event.description:
                    desc_lines = event.description.split('\n')
                    for line in desc_lines:
                        line = line.strip()
                        # Pattern pour professeur: "P.Nom" ou contient "prof"/"enseignant"
                        if any(keyword in line.lower() for keyword in ['prof', 'enseignant']) or \
                           (len(line.split()) <= 2 and '.' in line and len(line) < 20):
                            professeur = line
                            break

                cours_data = {
                    "nom_cours": nom_coupee,
                    "début": start_local.strftime('%Y-%m-%d %H:%M'),
                    "fin": end_local.strftime('%Y-%m-%d %H:%M'),
                    "description": description_coupee,
                    "professeur": professeur,
                    "location": getattr(event, 'location', '') or ''
                }
                
                cours_par_semaine[week_num].append(cours_data)
                stats["processed"] += 1
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur événement semaine: {e}")
                stats["errors"] += 1
                continue

        # Structure de retour organisée
        result = {
            "emploi_du_temps": [
                {
                    "semaine": week_num,
                    "evenements": sorted(events, key=lambda x: x["début"])
                }
                for week_num, events in sorted(cours_par_semaine.items())
            ],
            "revisions": [],  # Pour les événements ajoutés par l'IA
            "metadata": {
                "user_id": user_id,
                "total_weeks": len(cours_par_semaine),
                "generated_at": datetime.now().isoformat(),
                "stats": stats
            }
        }
        
        # Sauvegarder automatiquement
        json_dir = "json_schedules"
        os.makedirs(json_dir, exist_ok=True)
        json_file = os.path.join(json_dir, f"{user_id}_edt.json")
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Fichier sauvegardé: {json_file}")
        logger.info(f"📊 {stats['processed']} cours organisés en {len(cours_par_semaine)} semaines")
        
        # Affichage des premières semaines pour debug
        for semaine_data in result["emploi_du_temps"][:2]:
            week_num = semaine_data["semaine"]
            nb_events = len(semaine_data["evenements"])
            logger.info(f"📅 Semaine {week_num}: {nb_events} événement(s)")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur get_edt_semaine: {str(e)}")
        raise Exception(f"Impossible de récupérer l'emploi du temps: {str(e)}")
