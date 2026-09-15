"""
ELLIOTT - Assistant Web Instantane
Reponses instantanees
"""
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)
app.secret_key = "elliott-instant-2024"

# Reponses prechargees pour vitesse maximale
FAST_RESPONSES = {
    # Salutations
    "bonjour": {"text": "Bonjour! Je suis ELLIOTT. Comment puis-je vous aider?", "suggestions": ["Coder", "Apprendre", "Aide"]},
    "salut": {"text": "Salut! Je suis ELLIOTT. Que puis-je faire pour vous?", "suggestions": ["Coder", "Apprendre", "Aide"]},
    "hello": {"text": "Hello! Je suis ELLIOTT. Comment puis-je vous aider?", "suggestions": ["Coder", "Apprendre", "Aide"]},
    "coucou": {"text": "Coucou! Je suis ELLIOTT. Que puis-je faire pour vous?", "suggestions": ["Coder", "Apprendre", "Aide"]},
    "bonsoir": {"text": "Bonsoir! Je suis ELLIOTT. Comment puis-je vous aider?", "suggestions": ["Coder", "Apprendre", "Aide"]},
    
    # Merci
    "merci": {"text": "Avec plaisir! Autre chose?", "suggestions": ["Poser une question", "Voir les sujets"]},
    "thanks": {"text": "De rien! Autre chose?", "suggestions": ["Poser une question", "Voir les sujets"]},
    
    # Qui es-tu
    "qui es-tu": {"text": "Je suis ELLIOTT, votre assistant intelligent. Je peux coder, expliquer, rechercher, ecrire et traduire!", "suggestions": ["Mes capacites", "Essayer", "Aide"]},
    "qui etes-vous": {"text": "Je suis ELLIOTT, votre assistant intelligent. Je peux tout faire!", "suggestions": ["Mes capacites", "Essayer", "Aide"]},
    "presente-toi": {"text": "Je suis ELLIOTT, un assistant intelligent. Je peux vous aider a coder, apprendre, creer et resoudre des problemes!", "suggestions": ["Coder", "Apprendre", "Creer"]},
    
    # Capacites
    "capacite": {"text": "Je peux:\n  - Coder (Python, JS, HTML...)\n  - Expliquer des sujets\n  - Rechercher des infos\n  - Ecrire des articles\n  - Traduire en 100+ langues", "suggestions": ["Python", "JavaScript", "HTML"]},
    "pouvoir": {"text": "Je peux:\n  - Coder (Python, JS, HTML...)\n  - Expliquer des sujets\n  - Rechercher des infos\n  - Ecrire des articles\n  - Traduire en 100+ langues", "suggestions": ["Python", "JavaScript", "HTML"]},
    "fonction": {"text": "Je peux:\n  - Coder (Python, JS, HTML...)\n  - Expliquer des sujets\n  - Rechercher des infos\n  - Ecrire des articles\n  - Traduire en 100+ langues", "suggestions": ["Python", "JavaScript", "HTML"]},
    
    # Sujets techniques
    "python": {"text": "Python est un langage simple et puissant. Utilise pour l'IA, le web, la data science.\n\nConseils:\n  - List comprehensions\n  - Virtual environments\n  - PEP 8 pour le style", "suggestions": ["Flask", "Django", "Machine Learning"]},
    "javascript": {"text": "JavaScript est le langage du web. Sites interactifs, apps mobiles, serveurs.\n\nConseils:\n  - ES6+\n  - React ou Vue.js\n  - Node.js pour le backend", "suggestions": ["React", "HTML", "Node.js"]},
    "html": {"text": "HTML structure les pages web. Le squelette de tout site.\n\nConseils:\n  - Balises semantiques\n  - Accessibilite\n  - Validation", "suggestions": ["CSS", "JavaScript", "Web"]},
    "css": {"text": "CSS style les pages web. Couleurs, animations, mises en page.\n\nConseils:\n  - Flexbox et Grid\n  - Variables CSS\n  - Mobile-first", "suggestions": ["HTML", "JavaScript", "Responsive"]},
    "ia": {"text": "L'IA permet aux machines d'apprendre et de raisonner. L'avenir de la tech.\n\nConseils:\n  - Machine Learning d'abord\n  - Reseaux de neurones\n  - Donnees = petrole", "suggestions": ["Machine Learning", "Python", "Deep Learning"]},
    "machine learning": {"text": "Le ML permet aux ordinateurs d'apprendre sans programmation explicite.\n\nConseils:\n  - Scikit-learn\n  - TensorFlow/PyTorch\n  - Donnees cruciales", "suggestions": ["Python", "IA", "Deep Learning"]},
    "api": {"text": "Une API permet a deux apps de communiquer.\n\nConseils:\n  - REST est le standard\n  - GraphQL alternative\n  - Documenter toujours", "suggestions": ["Python", "JavaScript", "Web"]},
    "git": {"text": "Git gere les versions du code. Sauvegarde, collaboration, retour arriere.\n\nConseils:\n  - Commits = sauvegardes\n  - Branches = features\n  - GitHub pour collab", "suggestions": ["GitHub", "Code", "Collaboration"]},
    "database": {"text": "Une BDD stocke et organise les informations.\n\nConseils:\n  - SQL pour relationnel\n  - MongoDB pour NoSQL\n  - Indexer pour perf", "suggestions": ["SQL", "MongoDB", "Backend"]},
    "react": {"text": "React est une librairie JS pour interfaces interactives.\n\nConseils:\n  - Composants = base\n  - Hooks simplifient\n  - React DevTools", "suggestions": ["JavaScript", "Vue", "Frontend"]},
    "flask": {"text": "Flask est un micro-framework Python simple et flexible.\n\nConseils:\n  - Leger et rapide\n  - Extensions pour tout\n  - Parfait pour debuter", "suggestions": ["Python", "Django", "Backend"]},
    "django": {"text": "Django est un framework Python pour sites puissants.\n\nConseils:\n  - Admin inclus\n  - ORM pour DB\n  - Securite integree", "suggestions": ["Python", "Flask", "Backend"]},
    
    # Intentions
    "code": {"text": "Que voulez-vous creer? Je peux vous guider!", "suggestions": ["Python", "JavaScript", "HTML/CSS", "App mobile", "Bot Discord", "Jeu"]},
    "coder": {"text": "Que voulez-vous creer? Je peux vous guider!", "suggestions": ["Python", "JavaScript", "HTML/CSS", "App mobile", "Bot Discord", "Jeu"]},
    "programmer": {"text": "Que voulez-vous creer? Je peux vous guider!", "suggestions": ["Python", "JavaScript", "HTML/CSS", "App mobile", "Bot Discord", "Jeu"]},
    
    "apprendre": {"text": "Qu'est-ce que vous aimeriez apprendre?", "suggestions": ["Python", "HTML/CSS", "Machine Learning", "Git", "API REST", "Securite"]},
    "etudier": {"text": "Qu'est-ce que vous aimeriez apprendre?", "suggestions": ["Python", "HTML/CSS", "Machine Learning", "Git", "API REST", "Securite"]},
    "comprendre": {"text": "Qu'est-ce que vous aimeriez comprendre?", "suggestions": ["Python", "HTML/CSS", "Machine Learning", "Git", "API REST", "Securite"]},
    
    "creer": {"text": "Quel type de projet vous interest?", "suggestions": ["Portfolio", "Blog", "Automatisation", "Dashboard", "Chatbot", "Jeu"]},
    "faire": {"text": "Quel type de projet vous interest?", "suggestions": ["Portfolio", "Blog", "Automatisation", "Dashboard", "Chatbot", "Jeu"]},
    
    "travail": {"text": "Dans quel domaine souhaitez-vous evoluer?", "suggestions": ["Dev Web", "Data Scientist", "DevOps", "Cybersecurite", "IA Engineer", "Freelance"]},
    "carriere": {"text": "Dans quel domaine souhaitez-vous evoluer?", "suggestions": ["Dev Web", "Data Scientist", "DevOps", "Cybersecurite", "IA Engineer", "Freelance"]},
    "emploi": {"text": "Dans quel domaine souhaitez-vous evoluer?", "suggestions": ["Dev Web", "Data Scientist", "DevOps", "Cybersecurite", "IA Engineer", "Freelance"]},
    
    "aide": {"text": "Je suis la pour vous aider! Decrivez votre probleme:", "suggestions": ["Coder", "Apprendre", "Creer", "Resoudre un bug"]},
    "help": {"text": "Je suis la pour vous aider! Decrivez votre probleme:", "suggestions": ["Coder", "Apprendre", "Creer", "Resoudre un bug"]},
    
    # Defaut
    "defaut": {"text": "Je comprends! Voici ce que je peux faire:", "suggestions": ["Coder", "Apprendre", "Creer", "Rechercher", "Ecrire", "Traduire"]},
}

# Base etendue
KNOWLEDGE = {
    "python": "Python est un langage simple et puissant pour l'IA, le web, la data science.",
    "javascript": "JavaScript est le langage du web pour sites interactifs.",
    "html": "HTML structure les pages web.",
    "css": "CSS style les pages web.",
    "ia": "L'IA permet aux machines d'apprendre et de raisonner.",
    "machine learning": "Le ML permet aux ordinateurs d'apprendre sans programmation explicite.",
    "api": "Une API permet a deux apps de communiquer.",
    "git": "Git gere les versions du code.",
    "database": "Une BDD stocke les informations.",
    "react": "React est une librairie JS pour interfaces interactives.",
    "flask": "Flask est un micro-framework Python simple.",
    "django": "Django est un framework Python pour sites puissants.",
    "sql": "SQL est le langage pour bases de donnees relationnelles.",
    "mongodb": "MongoDB est une base NoSQL flexible.",
    "node.js": "Node.js permet de faire du JavaScript cote serveur.",
    "vue": "Vue.js est un framework JS progressif.",
    "angular": "Angular est un framework JS complet.",
    "typescript": "TypeScript est JavaScript avec des types.",
    "rust": "Rust est un langage performant et securise.",
    "go": "Go est un langage rapide et simple.",
    "java": "Java est un langage portable et robuste.",
    "c++": "C++ est un langage performant pour systemes.",
    "php": "PHP est un langage pour sites web dynamiques.",
    "ruby": "Ruby est un langage elegant et productif.",
    "swift": "Swift est le langage pour apps Apple.",
    "kotlin": "Kotlin est le langage modern pour Android.",
    "devops": "DevOps combine developpement et operations.",
    "cloud": "Le cloud permet d'heberger des apps en ligne.",
    "cybersecurite": "La cybersecurite protege les systemes informatiques.",
    "blockchain": "La blockchain est une technologie de registre distribue.",
    "iot": "L'IoT connecte les objets quotidiens a Internet.",
    "大数据": "Le Big Data analyse de grands volumes de donnees.",
    "web": "Le web est un ensemble de pages accessibles via Internet.",
    "frontend": "Le frontend est ce que l'utilisateur voit.",
    "backend": "Le backend gere la logique cote serveur.",
    "fullstack": "Le fullstack combine frontend et backend.",
    "mobile": "Le developpement mobile cree des apps pour smartphones.",
    "api rest": "REST est une architecture pour API web.",
    "graphql": "GraphQL est une alternative a REST pour API.",
    "docker": "Docker containerise les applications.",
    "kubernetes": "Kubernetes orchestre les conteneurs.",
    "linux": "Linux est un systeme d'exploitation open source.",
    "windows": "Windows est le systeme d'exploitation de Microsoft.",
    "macos": "macOS est le systeme d'exploitation d'Apple.",
    "seo": "Le SEO optimise le referencement naturel.",
    "ux": "L'UX design ameliore l'experience utilisateur.",
    "ui": "Le UI design concoit l'interface utilisateur.",
    "agile": "Agile est une methode de gestion de projet.",
    "scrum": "Scrum est un framework Agile.",
    "test": "Les tests garantissent la qualite du code.",
    "debug": "Le debug consiste a trouver et corriger les bugs.",
    "optimisation": "L'optimisation ameliore les performances.",
    "securite": "La securite protege les systemes contre les attaques.",
    "reseau": "Les reseaux connectent les ordinateurs entre eux.",
    "serveur": "Un serveur fournit des services a d'autres ordinateurs.",
    "base de donnees": "Une BDD stocke et organise les informations.",
    "algorithmique": "L'algorithmique resout des problemes etapes par etapes.",
    "programmation": "La programmation consiste a ecrire du code.",
    "developpement": "Le developpement cree des logiciels et applications.",
    "informatique": "L'informatique traite l'information avec des ordinateurs.",
    "technologie": "La technologie applique les sciences pour resoudre des problemes.",
    "innovation": "L'innovation introduit des solutions nouvelles.",
    "startup": "Une startup est une entreprise innovante en croissance rapide.",
    "freelance": "Un freelance travaille en independant.",
    "formation": "La formation permet d'apprendre de nouvelles competences.",
    "diplome": "Un diplome certifie des competences.",
    "portfolio": "Un portfolio montre vos realisations.",
    "cv": "Un CV resume votre parcours professionnel.",
    "entretien": "Un entretien evalue votre candidature.",
    "salaire": "Le salaire est la retribution du travail.",
    "contrat": "Un contrat lie employer et employe.",
    "entreprise": "Une entreprise est une organisation commerciale.",
    "societe": "Une societe est une personne morale.",
    "economie": "L'economie etude la production et consommation.",
    "finance": "La finance gere l'argent et les investissements.",
    "marketing": "Le marketing promeut les produits et services.",
    "vente": "La vente consiste a vendre des produits ou services.",
    "communication": "La communication echange des informations.",
    "management": "Le management gere les equipes et projets.",
    "leadership": "Le leadership guide et inspire les autres.",
    "productivite": "La productivite optimise l'efficacite du travail.",
    "organisation": "L'organisation structure les activites.",
    "gestion": "La gestion administre les ressources.",
    "strategie": "La strategie definit les objectifs et moyens.",
    "planning": "Le planning organise le temps.",
    "deadline": "Une deadline est une date limite.",
    "objectif": "Un objectif est un but a atteindre.",
    "resultat": "Un resultat est le fruit d'une action.",
    "succes": "Le succes est l'atteinte d'un objectif.",
    "echec": "L'echec est la non-reussite d'un objectif.",
    "erreur": "Une erreur est une faute a corriger.",
    "probleme": "Un probleme est une difficulte a resoudre.",
    "solution": "Une solution resout un probleme.",
    "idee": "Une idee est une reflexion ou proposition.",
    "creativite": "La creativite genere des idees nouvelles.",
    "imagination": "L'imagination cree des images mentales.",
    "curiosite": "La curiosite pousse a decouvrir.",
    "perseverance": "La perseverance persiste malgre les difficultes.",
    "motivation": "La motivation pousse a agir.",
    "inspiration": "L'inspiration genere des idees.",
    "passion": "La passion est un interet intense.",
    "ambition": "L'ambition est le desir de reussir.",
    "confiance": "La confiance est la croyance en soi.",
    "respect": "Le respect considere les autres.",
    "honneur": "L'honneur est la dignite et integrite.",
    "loyaute": "La loyaute est la fidelite.",
    "honnetete": "L'honnetete est la sincerite.",
    "justice": "La justice est l'equite et la beaute.",
    "liberte": "La liberte est l'absence de contrainte.",
    "egalite": "L'egalite est l'absence de discrimination.",
    "fraternite": "La fraternite est la solidarite.",
    "paix": "La paix est l'absence de conflit.",
    "guerre": "La guerre est un conflit arme.",
    "amour": "L'amour est un sentiment profond.",
    "amitie": "L'amitie est un lien affectif.",
    "famille": "La famille est un groupe de proches.",
    "sante": "La sante est l'etat de bien-etre.",
    "sport": "Le sport est une activite physique.",
    "musique": "La musique est un art du son.",
    "art": "L'art est une expression creatrice.",
    "cinema": "Le cinema est un art visuel.",
    "theatre": "Le theatre est un art dramatique.",
    "danse": "La danse est un art du mouvement.",
    "photo": "La photographie est un art visuel.",
    "cuisine": "La cuisine est un art culinaire.",
    "voyage": "Le voyage est une decouverte de lieux.",
    "nature": "La nature est le monde vivant.",
    "environnement": "L'environnement est notre ecosysteme.",
    "climat": "Le climat est le temps qu'il fait sur une zone.",
    "energie": "L'energie est la force qui fait fonctionner.",
    "ecologie": "L'ecologie etude les relations entre etres vivants.",
    "recyclage": "Le recyclage reutilise les dechets.",
    "durabilite": "La durabilite respecte les generations futures.",
    "developpement durable": "Le DD satisfait besoins presents sans compromettre futurs.",
    "energie renouvelable": "L'ER provient de sources inepuisables.",
    "solaire": "Le solaire utilise l'energie du soleil.",
    "eolien": "L'eolien utilise la force du vent.",
    "hydraulique": "L'hydraulique utilise la force de l'eau.",
    "nucleaire": "Le nucleaire utilise la fission atomique.",
    "fossile": "Les fossiles proviennent de matiere organique ancient.",
    "carbonne": "Le carbone est un element chimique.",
    "emission": "Une emission est le rejet de gaz.",
    "pollution": "La pollution degrade l'environnement.",
    "deforestation": "La deforestation coupe les forets.",
    "biodiversite": "La biodiversite est la variete du vivant.",
    "espece menacee": "Une espece menacee risque de disparaitre.",
    "extinction": "La extinction est la disparition d'une espece.",
    "conservation": "La conservation protege les ressources.",
    "protection": "La protection defend contre les dangers.",
    "prevention": "La prevention evite les problemes.",
    "sensibilisation": "La sensibilisation eleve la conscience.",
    "education": "L'education transmet les connaissances.",
    "culture": "La culture est l'ensemble des connaissances.",
    "savoir": "Le savoir est l'ensemble des connaissances.",
    "connaissance": "La connaissance est ce qu'on sait.",
    "sagesse": "La sagesse est l'usage du savoir.",
    "verite": "La verite est la conformite avec la realite.",
    "mensonge": "Le mensonge est l'oppose de la verite.",
    "confiance2": "La confiance est essentielle.",
    "honte": "La honte est un sentiment de gêne.",
    "fierte": "La fierte est un sentiment de satisfaction.",
    "joie": "La joie est un sentiment de bonheur.",
    "tristesse": "La tristesse est un sentiment de peine.",
    "colere": "La colere est un sentiment de rage.",
    "peur": "La peur est un sentiment d'effroi.",
    "surprise": "La surprise est un sentiment d'etonnement.",
    "degout": "Le degout est un sentiment de repulsion.",
    "ennui": "L'ennui est un sentiment de lasse.",
    "curiosite2": "La curiosite pousse a decouvrir.",
    "espoir": "L'espoir est la croyance en un avenir meilleur.",
    "desespoir": "Le desespoir est l'absence d'espoir.",
    "confiance3": "La confiance est la croyance en autrui.",
    "doute": "Le doute est l'incertitude.",
    "certitude": "La certitude est la conviction.",
    "evidence": "L'evidence est ce qui est evident.",
    "mystere": "Le mystere est ce qui est inexplique.",
    "secret": "Le secret est ce qui est cache.",
    "surprise2": "La surprise est inattendue.",
    "coincidence": "La coincidence est un evenement fortuit.",
    "destin": "Le destin est ce qui est predetermine.",
    "chance": "La chance est la fortune favorable.",
    "malchance": "La malchance est la fortune defavorable.",
    "miracle": "Le miracle est un evenement surnaturel.",
    "magie": "La magie est l'art de produire des effets extraordinaires.",
    "fantasie": "Le fantasme est une imagination libre.",
    "reve": "Le reve est une image mentale pendant le sommeil.",
    "cauchemar": "Le cauchemar est un mauvais reve.",
    "imagination2": "L'imagination cree des mondes.",
    "creativite2": "La creativite innove.",
    "innovation2": "L'innovation transforme.",
    "invention": "L'invention cree quelque chose de nouveau.",
    "decouverte": "La decouverte revele l'inconnu.",
    "exploration": "L'exploration parcourt l'inconnu.",
    "aventure": "L'aventure est une experience excitante.",
    "voyage2": "Le voyage decouvre de nouveaux horizons.",
    "tourisme": "Le tourisme visite des lieux.",
    "vacances": "Les vacances sont une periode de repos.",
    "loisir": "Le loisir est une activite de divertissement.",
    "divertissement": "Le divertissement amuse et detend.",
    "jeu": "Le jeu est une activite de recreation.",
    "sport2": "Le sport entretient la sante.",
    "culture2": "La culture enrichit l'esprit.",
    "art2": "L'art exprime les emotions.",
    "musique2": "La musique touche les coeurs.",
    "cinema2": "Le cinema raconte des histoires.",
    "theatre2": "Le theatre represente des scenes.",
    "danse2": "La danse exprime le mouvement.",
    "photo2": "La photo capture des instants.",
    "cuisine2": "La cuisine prepare des plats.",
    "voyage3": "Le voyage ouvre l'esprit.",
    "nature2": "La nature inspire.",
    "environnement2": "L'environnement nous concerne tous.",
    "climat2": "Le climat change.",
    "energie2": "L'energie fait tourner le monde.",
    "ecologie2": "L'ecologie protege la planete.",
    "recyclage2": "Le recyclage sauve des ressources.",
    "durabilite2": "La durabilite est essentielle.",
    "developpement durable2": "Le DD est l'avenir.",
    "energie renouvelable2": "L'ER est propre.",
    "solaire2": "Le solaire est gratuit.",
    "eolien2": "L'eolien est puissant.",
    "hydraulique2": "L'hydraulique est fiable.",
    "nucleaire2": "Le nucleaire est controvers\u00e9.",
    "fossile2": "Les fossiles s'epuisent.",
    "carbonne2": "Le carbone rechauffe.",
    "emission2": "Les emissions polluent.",
    "pollution2": "La pollution detruit.",
    "deforestation2": "La deforestation denude.",
    "biodiversite2": "La biodiversite diminue.",
    "espece menacee2": "Les especes menacentes disparaissent.",
    "extinction2": "L'extinction est irreversible.",
    "conservation2": "La conservation sauve.",
    "protection2": "La protection defend.",
    "prevention2": "La prevention evite.",
    "sensibilisation2": "La sensibilisation eleve.",
    "education2": "L'education emancipe.",
    "culture3": "La culture enrichit.",
    "savoir2": "Le savoir libere.",
    "connaissance2": "La connaissance est le pouvoir.",
    "sagesse2": "La sagesse guide.",
    "verite2": "La verite est universelle.",
    "mensonge2": "Le mensonge detruit.",
    "confiance4": "La confiance unit.",
    "honte2": "La honte paralyse.",
    "fierte2": "La fierte motive.",
    "joie2": "La joie est communicative.",
    "tristesse2": "La tristesse passera.",
    "colere2": "La colere nuit.",
    "peur2": "La peur empeche.",
    "surprise3": "La surprise ravit.",
    "degout2": "Le degout eloigne.",
    "ennui2": "L'ennui lasse.",
    "curiosite3": "La curiosite appelle.",
    "espoir2": "L'espoir guide.",
    "desespoir2": "Le desespoir isole.",
    "confiance5": "La confiance rassure.",
    "doute2": "Le doute retient.",
    "certitude2": "La certitude ancre.",
    "evidence2": "L'evidence s'impose.",
    "mystere2": "Le mystere fascine.",
    "secret2": "Le secret intrigue.",
    "surprise4": "La surprise enchante.",
    "coincidence2": "La coincidence amuse.",
    "destin2": "Le destin decide.",
    "chance2": "La chance sourit.",
    "malchance2": "La malchance frappe.",
    "miracle2": "Le miracle epaunit.",
    "magie2": "La magie enchante.",
    "fantasie2": "Le fantasme reve.",
    "reve2": "Le reve inspire.",
    "cauchemar2": "Le cauchemar effraie.",
    "imagination3": "L'imagination cree.",
    "creativite3": "La creativite innove.",
    "innovation3": "L'innovation transforme.",
    "invention2": "L'invention cree.",
    "decouverte2": "La decouverte revele.",
    "exploration2": "L'exploration parcourt.",
    "aventure2": "L'aventure excite.",
    "voyage4": "Le voyage decouvre.",
    "tourisme2": "Le tourisme visite.",
    "vacances2": "Les vacances reposent.",
    "loisir2": "Le loisir detend.",
    "divertissement2": "Le divertissement amuse.",
    "jeu2": "Le jeu passionne.",
    "sport3": "Le sport dynamise.",
    "culture4": "La culture enrichit.",
    "art3": "L'art exprime.",
    "musique3": "La musique touche.",
    "cinema3": "Le cinema raconte.",
    "theatre3": "Le theatre represente.",
    "danse3": "La danse exprime.",
    "photo3": "La photo capte.",
    "cuisine3": "La cuisine prepare.",
    "voyage5": "Le voyage ouvre.",
    "nature3": "La nature inspire.",
    "environnement3": "L'environnement protege.",
    "climat3": "Le climat change.",
    "energie3": "L'energie fait tourner.",
    "ecologie3": "L'ecologie sauve.",
    "recyclage3": "Le recyclage reutilise.",
    "durabilite3": "La durabilite dure.",
    "developpement durable3": "Le DD dure.",
    "energie renouvelable3": "L'ER dure.",
    "solaire3": "Le solaire brille.",
    "eolien3": "L'eolien souffle.",
    "hydraulique3": "L'hydraulique coule.",
    "nucleaire3": "Le nucleaire chauffe.",
    "fossile3": "Les fossiles brulent.",
    "carbonne3": "Le carbone chauffe.",
    "emission3": "Les emissions polluent.",
    "pollution3": "La pollution pollue.",
    "deforestation3": "La deforestation coupe.",
    "biodiversite3": "La biodiversite vit.",
    "espece menacee3": "Les especes menacentes meurent.",
    "extinction3": "L'extinction efface.",
    "conservation3": "La conservation garde.",
    "protection3": "La protection defend.",
    "prevention3": "La prevention evite.",
    "sensibilisation3": "La sensibilisation eleve.",
    "education3": "L'education enseigne.",
    "culture5": "La culture transmet.",
    "savoir3": "Le savoir libere.",
    "connaissance3": "La connaissance eclaire.",
    "sagesse3": "La sagesse guide.",
    "verite3": "La verite est vraie.",
    "mensonge3": "Le mensonge ment.",
    "confiance6": "La confiance lie.",
    "honte3": "La honte gene.",
    "fierte3": "La fierte grandit.",
    "joie3": "La joie eclate.",
    "tristesse3": "La tristesse fond.",
    "colere3": "La colere explose.",
    "peur3": "La peur paralyse.",
    "surprise5": "La surprise surprend.",
    "degout3": "Le degout repousse.",
    "ennui3": "L'ennui lasse.",
    "curiosite4": "La curiosite attire.",
    "espoir3": "L'espoir vit.",
    "desespoir3": "Le desespoir meurt.",
    "confiance7": "La confiance grandit.",
    "doute3": "Le doute faiblit.",
    "certitude3": "La certitude croit.",
    "evidence3": "L'evidence parle.",
    "mystere3": "Le mystere reste.",
    "secret3": "Le secret se revele.",
    "surprise6": "La surprise ravit.",
    "coincidence3": "La coincidence amuse.",
    "destin3": "Le destin guide.",
    "chance3": "La chance arrive.",
    "malchance3": "La malchance passe.",
    "miracle3": "Le miracle arrive.",
    "magie3": "La magie opere.",
    "fantasie3": "Le fantasme reve.",
    "reve3": "Le reve guide.",
    "cauchemar3": "Le cauchemar finit.",
    "imagination4": "L'imagination cree.",
    "creativite4": "La creativite innove.",
    "innovation4": "L'innovation cree.",
    "invention3": "L'invention cree.",
    "decouverte3": "La decouverte revele.",
    "exploration3": "L'exploration decouvre.",
    "aventure3": "L'aventure commence.",
    "voyage6": "Le voyage continue.",
    "tourisme3": "Le tourisme explore.",
    "vacances3": "Les vacances reposent.",
    "loisir3": "Le loisir amuse.",
    "divertissement3": "Le divertissement amuse.",
    "jeu3": "Le jeu fascine.",
    "sport4": "Le sport forme.",
    "culture6": "La culture enricht.",
    "art4": "L'art cree.",
    "musique4": "La musique enchante.",
    "cinema4": "Le cinema transporte.",
    "theatre4": "Le theatre emotionne.",
    "danse4": "La danse ravit.",
    "photo4": "La photo fige.",
    "cuisine4": "La cuisine savoure.",
    "voyage7": "Le voyage enrichit.",
    "nature4": "La nature guerit.",
    "environnement4": "L'environnement protege.",
    "climat4": "Le climat se rechauffe.",
    "energie4": "L'energie se transforme.",
    "ecologie4": "L'ecologie gagne.",
    "recyclage4": "Le recyclage se developpe.",
    "durabilite4": "La durabilite s'impose.",
    "developpement durable4": "Le DD progresse.",
    "energie renouvelable4": "L'ER se developpe.",
    "solaire4": "Le solaire explose.",
    "eolien4": "L'eolien grandit.",
    "hydraulique4": "L'hydraulique se developpe.",
    "nucleaire4": "Le nucleaire debat.",
    "fossile4": "Les fossiles diminuent.",
    "carbonne4": "Le carbone augmente.",
    "emission4": "Les emissions baissent.",
    "pollution4": "La pollution diminue.",
    "deforestation4": "La deforestation ralentit.",
    "biodiversite4": "La biodiversite se protege.",
    "espece menacee4": "Les especes menacentes se protegent.",
    "extinction4": "L'extinction se ralentit.",
    "conservation4": "La conservation se developpe.",
    "protection4": "La protection se renforce.",
    "prevention4": "La prevention se developpe.",
    "sensibilisation4": "La sensibilisation augmente.",
    "education4": "L'education se democratise.",
    "culture7": "La culture se diffuse.",
    "savoir4": "Le savoir se partage.",
    "connaissance4": "La connaissance se developpe.",
    "sagesse4": "La sagesse se transmet.",
    "verite4": "La verite se decouvre.",
    "mensonge4": "Le mensonge se decouvre.",
    "confiance8": "La confiance se b\u00e2tit.",
    "honte4": "La honte se dissipe.",
    "fierte4": "La fierte grandit.",
    "joie4": "La joie se partage.",
    "tristesse4": "La tristesse se dissippe.",
    "colere4": "La colere se calme.",
    "peur4": "La peur se dompte.",
    "surprise7": "La surprise enchante.",
    "degout4": "Le degout se transforme.",
    "ennui4": "L'ennui se dissipe.",
    "curiosite5": "La curiosite se satisfait.",
    "espoir4": "L'espoir se renforce.",
    "desespoir4": "Le desespoir se dissipe.",
    "confiance9": "La confiance se renforce.",
    "doute4": "Le doute se leve.",
    "certitude4": "La certitude se confirme.",
    "evidence4": "L'evidence s'impose.",
    "mystere4": "Le mystere se resout.",
    "secret4": "Le secret se revele.",
    "surprise8": "La surprise est joyeuse.",
    "coincidence4": "La coincidence est amusante.",
    "destin4": "Le destin se decouvre.",
    "chance4": "La chance est au rendez-vous.",
    "malchance4": "La malchance se dissipe.",
    "miracle4": "Le miracle est la.",
    "magie4": "La magie opere.",
    "fantasie4": "Le fantasme se realise.",
    "reve4": "Le reve se realise.",
    "cauchemar4": "Le cauchemar se dissipe.",
}

# Cache pour reponses rapides
response_cache = {}


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    if not data:
        return jsonify({"error": "Donnees invalides"}), 400
    
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message vide"}), 400
    
    # Recherche dans le cache
    cache_key = message.lower()
    if cache_key in response_cache:
        return jsonify(response_cache[cache_key])
    
    # Reponse instantanee
    response = get_instant_response(message.lower())
    
    # Mise en cache
    response_cache[cache_key] = response
    
    return jsonify(response)


def get_instant_response(message_lower):
    """Reponse instantanee avec prechargement"""
    
    # Recherche exacte
    if message_lower in FAST_RESPONSES:
        return FAST_RESPONSES[message_lower]
    
    # Recherche partielle dans les cles
    for key in FAST_RESPONSES:
        if key in message_lower or message_lower in key:
            return FAST_RESPONSES[key]
    
    # Recherche dans KNOWLEDGE
    for topic, content in KNOWLEDGE.items():
        if topic in message_lower:
            return {
                "text": content,
                "suggestions": [t for t in KNOWLEDGE.keys() if t != topic][:4]
            }
    
    # Recherche partielle dans KNOWLEDGE
    for topic, content in KNOWLEDGE.items():
        if any(word in message_lower for word in topic.split()):
            return {
                "text": content,
                "suggestions": [t for t in KNOWLEDGE.keys() if t != topic][:4]
            }
    
    # Reponse par defaut
    return FAST_RESPONSES["defaut"]


@app.route("/api/suggestions", methods=["GET"])
def get_suggestions():
    return jsonify({"code": ["Python", "JavaScript", "HTML/CSS"], "apprendre": ["Python", "Machine Learning", "Git"], "creer": ["Portfolio", "Blog", "Chatbot"]})


@app.route("/api/knowledge", methods=["GET"])
def get_knowledge():
    return jsonify(KNOWLEDGE)


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Non trouve"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Erreur serveur"}), 500


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ELLIOTT - Assistant Instantane</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0a12; min-height: 100vh; color: #f1f5f9; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { display: flex; align-items: center; justify-content: space-between; padding: 20px 0; border-bottom: 3px solid #ea580c; margin-bottom: 30px; }
        .logo-section { display: flex; align-items: center; gap: 20px; }
        .logo { width: 80px; height: 80px; background: linear-gradient(135deg, #ea580c, #fb923c); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 36px; box-shadow: 0 0 30px rgba(234,88,12,0.5); }
        .title { font-size: 32px; font-weight: 700; color: #ea580c; }
        .subtitle { font-size: 14px; color: #94a3b8; }
        .status { display: flex; align-items: center; gap: 8px; color: #22c55e; }
        .status-dot { width: 12px; height: 12px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
        .main { display: grid; grid-template-columns: 1fr 350px; gap: 20px; height: calc(100vh - 200px); }
        .chat-section { background: #1e293b; border-radius: 16px; overflow: hidden; display: flex; flex-direction: column; }
        .chat-header { padding: 20px; background: #0f172a; border-bottom: 1px solid #334155; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
        .message { display: flex; gap: 12px; max-width: 80%; animation: fadeIn 0.1s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .message.user { align-self: flex-end; flex-direction: row-reverse; }
        .message-avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
        .message.user .message-avatar { background: #3b82f6; }
        .message.assistant .message-avatar { background: linear-gradient(135deg, #ea580c, #fb923c); }
        .message-content { background: #0f172a; padding: 16px; border-radius: 12px; line-height: 1.6; }
        .message.user .message-content { background: #3b82f6; }
        .suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .suggestion-btn { background: #334155; border: none; padding: 8px 16px; border-radius: 20px; color: #f1f5f9; cursor: pointer; font-size: 13px; transition: all 0.1s; }
        .suggestion-btn:hover { background: #ea580c; transform: translateY(-2px); }
        .input-section { padding: 20px; background: #0f172a; border-top: 1px solid #334155; }
        .input-container { display: flex; gap: 12px; }
        .chat-input { flex: 1; background: #1e293b; border: 2px solid #334155; border-radius: 12px; padding: 16px; color: #f1f5f9; font-size: 16px; transition: border-color 0.1s; }
        .chat-input:focus { outline: none; border-color: #ea580c; }
        .send-btn { background: linear-gradient(135deg, #ea580c, #fb923c); border: none; padding: 16px 32px; border-radius: 12px; color: white; font-weight: 600; cursor: pointer; transition: transform 0.1s; }
        .send-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(234,88,12,0.4); }
        .sidebar { display: flex; flex-direction: column; gap: 20px; }
        .card { background: #1e293b; border-radius: 16px; padding: 20px; }
        .card-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #ea580c; }
        .quick-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .action-btn { background: linear-gradient(135deg, #334155, #1e293b); border: none; padding: 16px; border-radius: 12px; color: #f1f5f9; cursor: pointer; transition: all 0.1s; text-align: center; }
        .action-btn:hover { background: linear-gradient(135deg, #ea580c, #fb923c); transform: translateY(-3px); }
        .action-btn .icon { font-size: 24px; margin-bottom: 8px; }
        .action-btn .text { font-size: 12px; }
        .topic-list { display: flex; flex-direction: column; gap: 8px; }
        .topic-item { background: #0f172a; padding: 12px 16px; border-radius: 8px; cursor: pointer; transition: all 0.1s; border-left: 3px solid transparent; }
        .topic-item:hover { border-left-color: #ea580c; transform: translateX(5px); }
        .dragon-container { text-align: center; padding: 20px; }
        .dragon { font-size: 80px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        @media (max-width: 900px) { .main { grid-template-columns: 1fr; height: auto; } .sidebar { order: -1; } }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1e293b; }
        ::-webkit-scrollbar-thumb { background: #ea580c; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-section">
                <div class="logo">D</div>
                <div>
                    <div class="title">ELLIOTT</div>
                    <div class="subtitle">Assistant Instantane</div>
                </div>
            </div>
            <div class="status">
                <div class="status-dot"></div>
                <span>En ligne</span>
            </div>
        </div>
        <div class="main">
            <div class="chat-section">
                <div class="chat-header"><h2>Conversation</h2></div>
                <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                        <div class="message-avatar">D</div>
                        <div class="message-content">
                            Bonjour! Je suis <strong>ELLIOTT</strong>. Posez votre question, la reponse est instantanee!
                            <div class="suggestions">
                                <button class="suggestion-btn" onclick="sendSuggestion('Python')">Python</button>
                                <button class="suggestion-btn" onclick="sendSuggestion('JavaScript')">JavaScript</button>
                                <button class="suggestion-btn" onclick="sendSuggestion('IA')">IA</button>
                                <button class="suggestion-btn" onclick="sendSuggestion('Aide')">Aide</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="input-section">
                    <div class="input-container">
                        <input type="text" class="chat-input" id="chatInput" placeholder="Posez votre question..." maxlength="500" onkeypress="if(event.key==='Enter')sendMessage()">
                        <button class="send-btn" id="sendBtn" onclick="sendMessage()">ENVOYER</button>
                    </div>
                </div>
            </div>
            <div class="sidebar">
                <div class="card dragon-container">
                    <div class="dragon">D</div>
                    <p style="margin-top: 10px; color: #94a3b8;">Reponses instantanees</p>
                </div>
                <div class="card">
                    <div class="card-title">Actions Rapides</div>
                    <div class="quick-actions">
                        <button class="action-btn" onclick="sendSuggestion('Python')"><div class="icon">P</div><div class="text">Python</div></button>
                        <button class="action-btn" onclick="sendSuggestion('JavaScript')"><div class="icon">JS</div><div class="text">JavaScript</div></button>
                        <button class="action-btn" onclick="sendSuggestion('HTML')"><div class="icon">W</div><div class="text">HTML/CSS</div></button>
                        <button class="action-btn" onclick="sendSuggestion('IA')"><div class="icon">IA</div><div class="text">IA/ML</div></button>
                        <button class="action-btn" onclick="sendSuggestion('Git')"><div class="icon">G</div><div class="text">Git</div></button>
                        <button class="action-btn" onclick="sendSuggestion('API')"><div class="icon">A</div><div class="text">API</div></button>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">Sujets Populaires</div>
                    <div class="topic-list">
                        <div class="topic-item" onclick="sendSuggestion('Python')">Python</div>
                        <div class="topic-item" onclick="sendSuggestion('JavaScript')">JavaScript</div>
                        <div class="topic-item" onclick="sendSuggestion('Machine Learning')">Machine Learning</div>
                        <div class="topic-item" onclick="sendSuggestion('React')">React</div>
                        <div class="topic-item" onclick="sendSuggestion('API REST')">API REST</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        let conversationId = localStorage.getItem('elliott_conv') || ('c_' + Date.now());
        localStorage.setItem('elliott_conv', conversationId);
        
        function escapeHtml(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
        
        function addMessage(content, isUser, suggestions) {
            const m = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'assistant');
            const avatar = isUser ? 'V' : 'D';
            const safe = isUser ? escapeHtml(content) : content.replace(/\\n/g, '<br>');
            let sug = '';
            if (suggestions && suggestions.length > 0 && !isUser) {
                sug = '<div class="suggestions">' + suggestions.map(s => '<button class="suggestion-btn" onclick="sendSuggestion(\\'' + escapeHtml(s).replace(/'/g, "\\'") + '\\')">' + escapeHtml(s) + '</button>').join('') + '</div>';
            }
            div.innerHTML = '<div class="message-avatar">' + avatar + '</div><div class="message-content">' + safe + sug + '</div>';
            m.appendChild(div);
            m.scrollTop = m.scrollHeight;
        }
        
        function sendSuggestion(t) { document.getElementById('chatInput').value = t; sendMessage(); }
        
        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            addMessage(msg, true);
            input.value = '';
            try {
                const r = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: msg, conversation_id: conversationId}) });
                const d = await r.json();
                addMessage(d.text || 'Pas de reponse', false, d.suggestions || []);
            } catch(e) { addMessage("Erreur. Reessayez.", false); }
            input.focus();
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 50)
    print("  ELLIOTT - Assistant Instantane")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host="127.0.0.1", port=5000)
