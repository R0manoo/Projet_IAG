from datetime import datetime
from dotenv import load_dotenv
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_community.document_loaders import JSONLoader
import logging
import os


###################PATH VARIABLES###################
DATA_PATH = "data/"
FAISS_PATH = "faiss_data"
JSON_PATH ="json_schedules"
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

# Chargement des variables d'environnement
try:
    load_dotenv()
    logging.info("Variables d'environnement chargées")
except Exception as e:
    logging.error(f"Erreur dans le chargement des variables d'environnement: {repr(e)}")

# Configuration de l'API Key
try:
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")
    if not os.environ["OPENAI_API_KEY"]:
        raise ValueError("OPENAI_API_KEY non défini dans les variables d'environnement.")
except Exception as e:
    logging.error(f"Erreur lors de la définition de la clé API OpenAI: {repr(e)}")

# Initialisation des embeddings
try:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    logging.info("Modèle initialisé")
except Exception as e:
    logging.error(f"Erreur dans l'initialisation du modèle: {repr(e)}")

# Permet à la fonction metadata_func d'avoir acces à la variable user_id
def create_metadata_func(user_id):
    def metadata_func(record: dict, metadata: dict) -> dict:
        logging.info("Ajout des métadonnées")
        # Extract the start date from the record
        start_date_str = record.get('début')
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M")
            metadata['date'] = start_date.date().isoformat()  # Store the date in ISO format
        metadata['user_id'] = user_id
        metadata['source'] = f"http://applis.univ-nc.nc/cgi-bin/WebObjects/EdtWeb.woa/2/wa/default?login={user_id}%2Fical"
        return metadata
    return metadata_func

def json_to_documents(user_id):
    logging.info("Création du JSONLoader")
    loader = JSONLoader(
        file_path=f'{JSON_PATH}/{user_id}_edt.json',
        jq_schema=".emploi_du_temps[].evenements[]",
        metadata_func=create_metadata_func(user_id),  # Utilise la fonction métadata pour ajouter les métadonnées
        text_content=False
        )
    logging.info("Chargement des données JSON")
    documents = loader.load()
    # Ajoute des métadonnées à chaque document

    return documents

def load_faiss_vector_store():
    """
    Charge le vector store FAISS à partir du chemin spécifié.
    
    Returns:
        FAISS: L'instance du vector store FAISS chargée.
    """
    if os.path.exists(FAISS_PATH):
        try:
            vector_store = FAISS.load_local(FAISS_PATH, embeddings, allow_dangerous_deserialization=True)
            logging.info(f"Index FAISS local chargé depuis : {FAISS_PATH}")
            return vector_store
        except Exception as e:
            logging.error(f"Erreur lors du chargement de l'index FAISS : {repr(e)}")
            return None
    else:
        logging.info(f"Aucun index FAISS trouvé à {FAISS_PATH}")
        return None

def retrieve_documents(querry_text,filter_criteria, user_id, top_k=1):
    vector_store = load_faiss_vector_store()  # Charger le vector store ici
    if vector_store:
        try:
            # On recherche dans le vector store FAISS
            results = vector_store.similarity_search(
                querry_text,fetch_k=1000000 ,k=top_k, filter=filter_criteria
            )
            if results is not None:
                logging.info(f"{len(results)}informations intéressante trouvée pour {user_id}")
                return results
            else:
                logging.info("Aucune information intéressante trouvée")
        except Exception as e:
            logging.info(f"Erreur lors de la recherche de données : {repr(e)}")
    return None

def save_to_faiss(documents: list[Document]):
    """
    Sauvegarde un document à un vector store de FAISS.

    Args:
        documents (list[Document]): une liste de documents au format Langchain
    """
    try:
        vector_store = load_faiss_vector_store()
        # Création du vector store
        if not vector_store:
            logging.info("Création du vector store FAISS.")
            # Si le fichier n'existe pas, on le crée
            # On s'assure de toujours respecter les dimensions des vecteurs du modèle
            index = faiss.IndexFlatL2(len(embeddings.embed_query("hello world")))
            logging.info("Création du vector store FAISS.")
            vector_store = FAISS(
                embedding_function=embeddings,
                index=index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={}
            )
    except Exception as e:
        logging.error(f"Erreur lors de la création de l'index FAISS : {repr(e)}")
    try:
        vector_store.add_documents(documents=documents)
        logging.info(f"Ajout de {len(documents)} documents dans {FAISS_PATH}")
        vector_store.save_local(FAISS_PATH)
        logging.info(f"Vectors store sauvegardé localement dans {FAISS_PATH} ")
        
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde des documents dans FAISS : {repr(e)}")
