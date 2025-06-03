import logging
import os
import shutil
from faiss_handler import json_to_documents, retrieve_documents, save_to_faiss
from scrap_edt import get_edt_semaine_json

##################SETUP DES LOGS###################
# Ensure the logs directory exists
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)  # Create the directory if it doesn't exist


script_name = os.path.splitext(os.path.basename(__file__))[0]
log_file = os.path.join(log_dir, f"{script_name}.warn.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),  # Écrire dans le fichier log
        logging.StreamHandler()  # Écrire dans la console (terminal)
    ]
)
##############################################

def load_and_save_to_faiss_json(user_id):
    get_edt_semaine_json(user_id)
    docs=json_to_documents(user_id)
    save_to_faiss(docs)

def remove_data(file_path):
    if os.path.exists(file_path) and os.path.isdir(file_path):
        try:
            for file_name in os.listdir(file_path):
                file_path = os.path.join(file_path, file_name)
                # Check if it is a file before deleting
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logging.info(f"{file_name} supprimé" )
        except Exception as e:
                logging.error(f"Une erreur est survenu lors de la suppression des fichiers: {e}")
    else:
        logging.info(f"Le chemin : '{file_path}' n'existe pas.")


def filter_data_userId(list_of_dates,user_id)->dict:
    return {
        "date": list_of_dates,
        "user_id":user_id
    }

def fetch_and_concatenate_documents(query_text, list_of_dates, user_id, top_k=65):
    """
    Récupère les documents pertinents à partir de FAISS, les concatène et retourne le contexte.

    Args:
        query_text (str): Le texte de la requête.
        list_of_dates (list[str]): Liste des dates pour filtrer les documents.
        user_id (str): L'utilisateur pour lequel les documents sont récupérés.
        top_k (int): Nombre maximum de documents à récupérer.

    Returns:
        str: Contexte concaténé des documents récupérés.
    """
    
    try:
        # Récupération des documents pertinents
        edt = retrieve_documents(query_text, filter_data_userId(list_of_dates, user_id), user_id, top_k=top_k)
        
        if edt:
            for doc in edt:
                logging.info(f"Document récupéré pour {user_id}: \n {doc.page_content}")
            
            # Concaténation des documents pour former le contexte
            context = "\n\n".join([doc.page_content for doc in edt])
            logging.info(f"Contexte final pour {user_id}: \n {context}")
            
            return context
        else:
            logging.info(f"Aucun document pertinent trouvé pour l'utilisateur {user_id}.")
            return ""
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des documents pour {user_id}: {repr(e)}")
        return ""
