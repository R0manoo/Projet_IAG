from collections import defaultdict
import os
import openai
import requests
from ics import Calendar
import pytz
from dotenv import load_dotenv
import json

load_dotenv()


openai.api_key = os.getenv("OPENAI_KEY")

# Fonction pour récupérer l'EDT depuis l'URL ICS
def get_edt(user_id):
    """Récupère l'emploi du temps (EDT) d'un utilisateur à partir d'une URL ICS.

    Cette fonction fait une requête GET pour obtenir le calendrier ICS d'un utilisateur
    via son identifiant. Elle extrait les événements du calendrier et les formate
    en une liste de dictionnaires contenant les détails des cours.

    Args:
        user_id (str): L'identifiant de l'utilisateur pour lequel récupérer l'emploi du temps.

    Raises:
        Exception: Si la requête échoue ou si l'identifiant est invalide.

    Returns:
        List[Dict[str, str]]: Une liste de dictionnaires, chaque dictionnaire représentant
        un cours avec les clés suivantes :
            - "nom_cours": Le nom du cours (str).
            - "début": La date et l'heure de début du cours au format 'YYYY-MM-DD HH:MM' (str).
            - "fin": La date et l'heure de fin du cours au format 'YYYY-MM-DD HH:MM' (str).
            - "description": La description du cours (str).
    """
  
    ics_url = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
    response = requests.get(ics_url)

    # S'assurer de l'encodage UTF-8
    response.encoding = "UTF-8"
    
    if response.ok:
        ics_content = response.text
    else:
        raise Exception("Veuillez entrer un identifiant valide 🚫")

    cal = Calendar(ics_content)
    cours = []

    local_tz = pytz.timezone("Pacific/Noumea")

    for event in cal.events:
        start_local = event.begin.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')
        end_local = event.end.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')

        description_coupee = event.description.split('(')[0].strip() #réduire le nom du cours pour l'utilisation dans le chatbot
        nom_coupee = event.name.split('(')[0].strip() #réduire le nom du cours pour l'utilisation dans le chatbot
        cours.append({
            "nom_cours": nom_coupee,
            "début": start_local,
            "fin": end_local,
            "description": description_coupee
        })

    return cours

def get_edt_semaine(user_id):
    """Récupère l'emploi du temps (EDT) d'un utilisateur pour la semaine à partir d'une URL ICS.

    Cette fonction récupère les événements d'un calendrier ICS et les organise par semaine.

    Args:
        user_id (str): L'identifiant de l'utilisateur pour lequel récupérer l'emploi du temps.

    Raises:
        Exception: Si la requête échoue ou si l'identifiant est invalide.

    Returns:
        List[List[Dict[str, str]]]: Une liste de listes, chaque sous-liste représentant une semaine
        de cours avec les détails du cours :
            - "nom_cours": Le nom du cours (str).
            - "début": La date et l'heure de début du cours au format 'YYYY-MM-DD HH:MM' (str).
            - "fin": La date et l'heure de fin du cours au format 'YYYY-MM-DD HH:MM' (str).
            - "description": La description du cours (str).
    """
  
    ics_url = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
    response = requests.get(ics_url)

    # S'assurer de l'encodage UTF-8
    response.encoding = "UTF-8"
    
    if response.ok:
        ics_content = response.text
    else:
        raise Exception("Veuillez entrer un identifiant valide 🚫")

    cal = Calendar(ics_content)
    cours_par_semaine = defaultdict(list)

    local_tz = pytz.timezone("Pacific/Noumea")

    for event in cal.events:
        start_local = event.begin.astimezone(local_tz)
        end_local = event.end.astimezone(local_tz)

        # Obtenir le numéro de la semaine
        week_num = start_local.isocalendar()[1]
        
        description_coupee = event.description.split('(')[0].strip()
        nom_coupee = event.name.split('(')[0].strip()

        # Ajouter le cours à la semaine correspondante
        cours_par_semaine[week_num].append({
            "nom_cours": nom_coupee,
            "début": start_local.strftime('%Y-%m-%d %H:%M'),
            "fin": end_local.strftime('%Y-%m-%d %H:%M'),
            "description": description_coupee
        })

    # Convertir le defaultdict en une liste de listes, triée par semaine
    cours_semaine_list = [cours for _, cours in sorted(cours_par_semaine.items())]

    return cours_semaine_list



def get_edt_semaine_json(user_id):
    """Récupère l'emploi du temps (EDT) d'un utilisateur pour la semaine, organise les données, 
       et les sauvegarde en format JSON.

    Args:
        user_id (str): L'identifiant de l'utilisateur pour lequel récupérer l'emploi du temps.

    Raises:
        Exception: Si la requête échoue ou si l'identifiant est invalide.

    Returns:
        str: Une chaîne JSON représentant les données structurées par semaine.
    """
  
    ics_url = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
    response = requests.get(ics_url)

    # S'assurer de l'encodage UTF-8
    response.encoding = "UTF-8"
    
    if response.ok:
        ics_content = response.text
    else:
        raise Exception("Veuillez entrer un identifiant valide 🚫")

    cal = Calendar(ics_content)
    cours_par_semaine = defaultdict(list)
    local_tz = pytz.timezone("Pacific/Noumea")

    for event in cal.events:
        start_local = event.begin.astimezone(local_tz)
        end_local = event.end.astimezone(local_tz)

        # Obtenir le numéro de la semaine
        week_num = start_local.isocalendar()[1]
        
        # Extraire les informations spécifiques du nom et description et prof
        nom_cours = event.name.split('(')[0].strip()
        description_lignes = event.description.split("\n")        
        
        professeur = description_lignes[1].strip() if len(description_lignes) > 1 else 'Inconnu'


        # Ajouter le cours structuré à la semaine correspondante
        cours_par_semaine[week_num].append({
            'nom_cours': nom_cours,
            'début': start_local.strftime('%Y-%m-%d %H:%M'),
            'fin': end_local.strftime('%Y-%m-%d %H:%M'),
            'professeur' : professeur
        })
        
    # Trier les événements dans chaque semaine par date de début
    for semaine, cours in cours_par_semaine.items():
        cours.sort(key=lambda x: x["début"])  # Tri par la date de début


    # Convertir le defaultdict en une liste de dictionnaires structurés par semaine
    emploi_du_temps = [
        {
            "semaine": semaine,
            "evenements": cours
        }
        for semaine, cours in sorted(cours_par_semaine.items())
    ]

    # Convertir en JSON
    cours_json = json.dumps({"emploi_du_temps": emploi_du_temps}, ensure_ascii=False, indent=4)
    
    # Sauvegarder le JSON dans un fichier local
    directory = "json_schedules"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    file_path = os.path.join(directory, f"{user_id}_edt.json")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(cours_json)
    print(f"Fichier sauvegardé sous : {file_path}")

    return cours_json

