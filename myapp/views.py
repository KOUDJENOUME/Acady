from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404
from .models import Eleve , Note , Login
from django.db.models import Sum, Avg, Sum, F, FloatField
from django.core.paginator import Paginator
from datetime import datetime
import os
import sys
from django.contrib.auth.hashers import check_password, make_password

def choix_role(request):
    return render(request, "choix_role.html")

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import random
from .models import Enseignant

# ------------------------------
# INSCRIPTION ENSEIGNANT
# ------------------------------
def register_enseignant(request):
    context = {}
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        prenoms = request.POST.get('prenoms')
        email = request.POST.get('email')
        password = request.POST.get('password')
        matieres = request.POST.getlist('matieres')
        classes = request.POST.getlist('classes')
        annee_academique = request.POST.get('annee_academique')

        # Vérifier si email existe déjà
        if Enseignant.objects.filter(email=email).exists():
            context['error'] = "Cet email est déjà utilisé."
            return render(request, 'enseignant/register.html', context)

        # Vérifier conflit matière/classe
        conflit = []
        for mat in matieres:
            for cls in classes:
                if Enseignant.objects.filter(classes__icontains=cls, matiere__icontains=mat).exists():
                    conflit.append(f"{mat} - {cls}")

        if conflit:
            context['error'] = f"Impossible d'assigner ces matières aux classes car elles sont déjà prises : {', '.join(conflit)}"
            return render(request, 'enseignant/register.html', context)

        # Hacher le mot de passe
        hashed_password = make_password(password)

        # Création de l'enseignant
        enseignant = Enseignant.objects.create(
            nom=nom,
            prenoms=prenoms,
            email=email,
            password=hashed_password,
            matiere=",".join(matieres),
            classes=",".join(classes),
            annee_academique=annee_academique
        )

        messages.success(request, "Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.")
        return redirect('enseignant_login')


    return render(request, 'enseignant/register.html', context)

# ------------------------------
# LOGIN ENSEIGNANT
# ------------------------------
def enseignant_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            enseignant = Enseignant.objects.get(email=email)
            
            # Vérifier mot de passe haché
            if check_password(password, enseignant.password):
                otp_code = str(random.randint(100000, 999999))
                enseignant.otp_code = otp_code
                enseignant.otp_timestamp = timezone.now()
                enseignant.save()

                send_mail(
                    'Code de connexion',
                    f'Bonjour {enseignant.nom}, votre code de connexion est : {otp_code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [enseignant.email],
                    fail_silently=False
                )

                request.session['temp_enseignant_id'] = enseignant.id
                messages.success(request, 'Un code a été envoyé à votre email. Il expire dans 120 secondes.')
                return redirect('enseignant_verification_otp')
            else:
                messages.error(request, 'Mot de passe incorrect.')

        except Enseignant.DoesNotExist:
            messages.error(request, 'Aucun compte trouvé avec cet email.')

    return render(request, 'enseignant/login.html')

# ------------------------------
# VERIFICATION OTP LOGIN
# ------------------------------
def enseignant_verification_otp(request):
    if request.method == "POST":
        code_saisi = request.POST.get("otp")
        enseignant_id = request.session.get("temp_enseignant_id")

        if not enseignant_id:
            messages.error(request, "Session expirée, veuillez vous reconnecter.")
            return redirect("enseignant_login")

        try:
            enseignant = Enseignant.objects.get(id=enseignant_id)
            now = timezone.now()

            if enseignant.otp_code and enseignant.otp_timestamp:
                delta = now - enseignant.otp_timestamp

                if delta.total_seconds() <= 120:
                    if code_saisi == enseignant.otp_code:
                        request.session['enseignant_id'] = enseignant.id
                        request.session['enseignant_nom'] = f"{enseignant.nom} {enseignant.prenoms}"
                        request.session['enseignant_matiere'] = enseignant.matiere

                        # Supprimer OTP
                        enseignant.otp_code = None
                        enseignant.otp_timestamp = None
                        enseignant.save()
                        del request.session['temp_enseignant_id']

                        messages.success(request, f"Bienvenue {enseignant.nom} {enseignant.prenoms} !")
                        return redirect('dashboard_enseignant')
                    else:
                        messages.error(request, "Code incorrect.")
                else:
                    messages.error(request, "Code expiré. Un nouveau code est envoyé.")
                    # Générer nouveau code automatiquement
                    otp_code = str(random.randint(100000, 999999))
                    enseignant.otp_code = otp_code
                    enseignant.otp_timestamp = timezone.now()
                    enseignant.save()
                    send_mail(
                        'Nouveau code de connexion',
                        f'Bonjour {enseignant.nom}, votre nouveau code de connexion est : {otp_code}',
                        settings.DEFAULT_FROM_EMAIL,
                        [enseignant.email],
                        fail_silently=False
                    )
            else:
                messages.error(request, "Pas de code OTP généré. Veuillez vous reconnecter.")

        except Enseignant.DoesNotExist:
            messages.error(request, "Utilisateur introuvable.")

    return render(request, "enseignant/verification_otp.html")

# ------------------------------
# MOT DE PASSE OUBLIE
# ------------------------------
import threading
from django.core.mail import send_mail
from django.conf import settings

def enseignant_mdp_oublie(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            enseignant = Enseignant.objects.get(email=email)
            otp = str(random.randint(100000, 999999))
            enseignant.otp_code = otp
            enseignant.otp_timestamp = timezone.now()
            enseignant.save()

            # Envoi async dans un thread séparé
            def send_otp_email():
                try:
                    send_mail(
                        "Code de réinitialisation",
                        f"Votre code est : {otp}",
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False
                    )
                except Exception as e:
                    print(f"Erreur email: {e}")  # Log l'erreur

            # Lance le thread
            email_thread = threading.Thread(target=send_otp_email)
            email_thread.daemon = True  # Thread se termine avec le programme
            email_thread.start()

            request.session["reset_enseignant_id"] = enseignant.id
            messages.success(request, "Un code a été envoyé à votre email.")
            return redirect("enseignant_mdp_oublie_otp")

        except Enseignant.DoesNotExist:
            messages.error(request, "Aucun compte trouvé avec cet email.")

    return render(request, "enseignant/mdp_oublie_email.html")
# ------------------------------
# OTP POUR RESET MOT DE PASSE
# ------------------------------
def enseignant_mdp_oublie_otp(request):
    enseignant_id = request.session.get("reset_enseignant_id")

    if enseignant_id is None:
        return redirect("enseignant_mdp_oublie")

    enseignant = Enseignant.objects.get(id=enseignant_id)

    if request.method == "POST":
        otp = request.POST.get("otp")
        if otp == enseignant.otp_code:
            diff = timezone.now() - enseignant.otp_timestamp
            if diff.total_seconds() <= 120:
                return redirect("enseignant_mdp_oublie_reset")
            else:
                messages.error(request, "Le code a expiré.")
        else:
            messages.error(request, "Code incorrect.")

    return render(request, "enseignant/mdp_oublie_otp.html")

# ------------------------------
# RESET MOT DE PASSE
# ------------------------------
import re
def password_is_valid(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[0-9]", password)
    )

def enseignant_mdp_oublie_reset(request):
    enseignant_id = request.session.get("reset_enseignant_id")

    if enseignant_id is None:
        return redirect("enseignant_mdp_oublie")

    enseignant = Enseignant.objects.get(id=enseignant_id)

    if request.method == "POST":
        p1 = request.POST.get("password1")
        p2 = request.POST.get("password2")

        if p1 != p2:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            return redirect("enseignant_mdp_oublie_reset")

        if not password_is_valid(p1):
            messages.error(request, 
                "❌ Le mot de passe doit contenir au minimum 8 caractères, "
                "au moins 1 chiffre et 1 symbole."
            )
            return redirect("enseignant_mdp_oublie_reset")

        # Hacher le mot de passe
        enseignant.password = make_password(p1)
        enseignant.otp_code = None
        enseignant.save()

        del request.session["reset_enseignant_id"]

        messages.success(request, "✅ Mot de passe réinitialisé avec succès ! Connectez-vous.")
        return redirect("enseignant_login")

    return render(request, "enseignant/mdp_oublie_reset.html")

def dashboard_enseignant(request):
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        return redirect('enseignant_login')

    try:
        enseignant = Enseignant.objects.get(id=enseignant_id)
    except Enseignant.DoesNotExist:
        return redirect('enseignant_login')

    if enseignant.matiere:
        enseignant.matieres_list = enseignant.matiere.split(",")
    else:
        enseignant.matieres_list = []

    classes = enseignant.classes.split(",") if enseignant.classes else []
    classes_data = []

    for c in classes:
        horaires = Horaire.objects.filter(classe=c, enseignant=enseignant)
        classes_data.append({
            'nom': c,
            'annee_academique': enseignant.annee_academique,
            'horaires': horaires
        })

    school_name = "CPEG LE TRÉSOR DE DOWA"

    # Récupérer les messages spécifiques via GET
    success_message = request.GET.get('success', None)
    error_message = request.GET.get('error', None)

    return render(request, 'enseignant/dashboard.html', {
        'enseignant': enseignant,
        'classes': classes_data,
        'school_name': school_name,
        'success': success_message,
        'error': error_message
    })

def enseignant_logout(request):
    request.session.flush()  # supprime toutes les données de session
    return redirect('enseignant_login')

def inscription(request):
    if request.method == "POST":
        # Vérifier si un compte existe déjà
        if Login.objects.exists():  
            messages.error(request, "Un compte existe déjà. Impossible d'en créer un autre.")
            return redirect("inscription")

        # Récupérer les informations du formulaire
        username = request.POST.get("username")
        name = request.POST.get("name")
        school_name = request.POST.get("school_name")
        password = request.POST.get("password")  # simplement enregistré tel quel
        email = request.POST.get("email")
        numero = request.POST.get("numero")
        profile_image = request.FILES.get("profile_image")
        coin_droit = request.FILES.get('coin_droit')
        fond_verso = request.FILES.get('fond_verso')

        # Créer et enregistrer l'utilisateur
        new_user = Login(
            username=username,
            name=name,
            school_name=school_name,
            password=password,  # mot de passe simple
            email=email,
            numero=numero,
            profile_image=profile_image,
            coin_droit=coin_droit,
            fond_verso=fond_verso
        )
        new_user.save()

        messages.success(request, "Compte créé avec succès. Connectez-vous !")
        return redirect("login")
    
    return render(request, "sign_up.html")


def reset_utilisateurs(request):
    # Supprimer tous les utilisateurs de la base de données
    Login.objects.all().delete()

    messages.success(request, "Tous les comptes ont été supprimés !")
    return redirect("inscription")  # Redirige vers la page d'inscription


def connexion(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Vérifier si les identifiants existent dans la base de données
        user = Login.objects.filter(username=username, password=password).first()

        if user:

            return redirect("accueil")  # Redirige vers la page d'accueil
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    
    return render(request, "login.html")

def accueil_view(request):
    
    # Récupérer l'année actuelle
    current_year = datetime.now().year

    # Déterminer l'année académique en fonction de l'année actuelle
    if datetime.now().month < 9:  # Avant septembre, l'année académique commence l'année suivante
        annee_academique = f"{current_year - 1}-{current_year}"
    else:  # Après septembre, l'année académique commence l'année en cours
        annee_academique = f"{current_year}-{current_year + 1}"

    # Utiliser cette valeur comme valeur par défaut dans la requête GET
    annee_academique = request.GET.get('annee', annee_academique)
    # Filtrer les statistiques par classe et année académique
    statistiques_sixieme = {
        'garçons': Eleve.objects.filter(classe="6ème", sexe="M", annee_academique=annee_academique).count(),
        'filles': Eleve.objects.filter(classe="6ème", sexe="F", annee_academique=annee_academique).count(),
        'total_eleves': Eleve.objects.filter(classe="6ème", annee_academique=annee_academique).count(),
    }

    statistiques_cinquieme = {
        'garçons': Eleve.objects.filter(classe="5ème", sexe="M", annee_academique=annee_academique).count(),
        'filles': Eleve.objects.filter(classe="5ème", sexe="F", annee_academique=annee_academique).count(),
        'total_eleves': Eleve.objects.filter(classe="5ème", annee_academique=annee_academique).count(),
    }

    statistiques_quatrieme = {
        'garçons': Eleve.objects.filter(classe="4ème", sexe="M", annee_academique=annee_academique).count(),
        'filles': Eleve.objects.filter(classe="4ème", sexe="F", annee_academique=annee_academique).count(),
        'total_eleves': Eleve.objects.filter(classe="4ème", annee_academique=annee_academique).count(),
    }

    statistiques_troisieme = {
        'garçons': Eleve.objects.filter(classe="3ème", sexe="M", annee_academique=annee_academique).count(),
        'filles': Eleve.objects.filter(classe="3ème", sexe="F", annee_academique=annee_academique).count(),
        'total_eleves': Eleve.objects.filter(classe="3ème", annee_academique=annee_academique).count(),
    }
   # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""
    return render(request, 'accueil.html', {
        'statistiques_sixieme': statistiques_sixieme,
        'statistiques_cinquieme': statistiques_cinquieme,
        'statistiques_quatrieme': statistiques_quatrieme,
        'statistiques_troisieme': statistiques_troisieme,
        'annee_academique': annee_academique,  # Pour l'affichage dans le HTML
        'school_name': school_name,
    })


def enregistrer_eleve(request):
    if request.method == 'POST':
        # Récupération des champs
        nom = request.POST.get('nom')
        prenoms = request.POST.get('prenoms')
        matricule = request.POST.get('matricule')
        sexe = request.POST.get('sexe')
        classe = request.POST.get('classe')
        annee_academique = request.POST.get('annee_academique')
        telephone_parent = request.POST.get('telephone_parent')
        email_parent = request.POST.get('email_parent')
        profile_eleve = request.FILES.get("profile_eleve")
        date_naissance = request.POST.get("date_naissance")  # facultatif
        lieu_naissance = request.POST.get("lieu_naissance")  # facultatif
        nationalite = request.POST.get("nationalite")        # facultatif

        # Vérifier si l'élève existe déjà
        exists_in_Eleve = Eleve.objects.filter(
            nom=nom,
            prenoms=prenoms,
            matricule=matricule,
            sexe=sexe,
            classe=classe,
            annee_academique=annee_academique,
            telephone_parent=telephone_parent,
            email_parent=email_parent
        ).exists()

        if exists_in_Eleve:
            messages.error(request, "L'élève existe déjà")
        else:
            # Enregistrement de l'élève
            Eleve.objects.create(
                nom=nom,
                prenoms=prenoms,
                matricule=matricule,
                sexe=sexe,
                classe=classe,
                annee_academique=annee_academique,
                telephone_parent=telephone_parent,
                email_parent=email_parent,
                profile_eleve=profile_eleve,
                date_naissance=date_naissance if date_naissance else None,
                lieu_naissance=lieu_naissance if lieu_naissance else None,
                nationalite=nationalite if nationalite else None
            )
            messages.success(request, "Élève enregistrée avec succès.")

    # Récupérer l'école
    user = Login.objects.first()
    school_name = user.school_name if user else ""

    return render(request, 'enregistrer_eleve.html', {'school_name': school_name})

def modifier_eleve(request, classe, eleve_id, annee):
    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)
    annee_academique = annee

    if request.method == "POST":
        # Récupération des champs
        nom = request.POST.get("nom")
        prenoms = request.POST.get("prenoms")
        matricule = request.POST.get("matricule")
        sexe = request.POST.get("sexe")
        new_classe = request.POST.get("classe")
        new_annee = request.POST.get("annee_academique")
        telephone_parent = request.POST.get("telephone_parent")
        email_parent = request.POST.get("email_parent")
        date_naissance = request.POST.get("date_naissance")
        lieu_naissance = request.POST.get("lieu_naissance")
        nationalite = request.POST.get("nationalite")

        # Récupère la nouvelle image seulement si l'utilisateur en charge une
        new_image = request.FILES.get("profile_eleve")

        # Validation minimale des champs obligatoires
        if not all([nom, prenoms, sexe, new_classe, new_annee]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
        else:
            # Mise à jour des données
            eleve.nom = nom
            eleve.prenoms = prenoms
            eleve.matricule = matricule
            eleve.sexe = sexe
            eleve.classe = new_classe
            eleve.annee_academique = new_annee
            eleve.telephone_parent = telephone_parent
            eleve.email_parent = email_parent
            eleve.date_naissance = date_naissance if date_naissance else None
            eleve.lieu_naissance = lieu_naissance
            eleve.nationalite = nationalite

            if new_image:
                eleve.profile_eleve = new_image

            eleve.save()
            messages.success(request, "Les informations de l'élève ont été modifiées avec succès.")

    # Récupérer l'école
    user = Login.objects.first()
    school_name = user.school_name if user else ""

    return render(request, "modifier_eleve.html", {
        "eleve": eleve,
        "classe": classe,
        "school_name": school_name,
        "annee_academique": annee_academique
    })

def afficher_sixieme(request,annee):
    # Récupérer l'année académique depuis les paramètres GET
    annee_academique = request.GET.get('annee',annee)

    # Filtrer les élèves par classe, et éventuellement par année académique
    if annee_academique:
        eleves = Eleve.objects.filter(classe="6ème", annee_academique=annee_academique).order_by('nom','prenoms')
    else:
        eleves = Eleve.objects.filter(classe="6ème").order_by('nom','prenoms')
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""

    return render(request, 'listes_classes/6ème.html', {
        'eleves': eleves,
        'classe': "6ème",
        "school_name": school_name,
        'annee_academique': annee_academique  # Passer l'année sélectionnée pour pré-remplir le champ dans le formulaire
    })
def afficher_cinquieme(request,annee):
     # Récupérer l'année académique depuis les paramètres GET
    annee_academique = request.GET.get('annee',annee)
    # Filtrer les élèves par classe, et éventuellement par année académique
    if annee_academique:
        eleves = Eleve.objects.filter(classe="5ème", annee_academique=annee_academique).order_by('nom','prenoms')
    else:
        eleves = Eleve.objects.filter(classe="5ème").order_by('nom','prenoms')
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""

    return render(request, 'listes_classes/5ème.html', {
        'eleves': eleves,
        "school_name": school_name,
        'classe': "5ème",
        'annee_academique': annee_academique  # Passer l'année sélectionnée pour pré-remplir le champ dans le formulaire
    })

def afficher_quatrieme(request,annee):
     # Récupérer l'année académique depuis les paramètres GET
    annee_academique = request.GET.get('annee',annee)

    # Filtrer les élèves par classe, et éventuellement par année académique
    if annee_academique:
        eleves = Eleve.objects.filter(classe="4ème", annee_academique=annee_academique).order_by('nom','prenoms')
    else:
        eleves = Eleve.objects.filter(classe="4ème").order_by('nom','prenoms')
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""

    return render(request, 'listes_classes/4ème.html', {
        'eleves': eleves,
        "school_name": school_name,
        'classe': "4ème",
        'annee_academique': annee_academique  # Passer l'année sélectionnée pour pré-remplir le champ dans le formulaire
    })

def afficher_troisieme(request,annee):
    # Récupérer l'année académique depuis les paramètres GET
    annee_academique = request.GET.get('annee',annee)

    # Filtrer les élèves par classe, et éventuellement par année académique
    if annee_academique:
        eleves = Eleve.objects.filter(classe="3ème", annee_academique=annee_academique).order_by('nom','prenoms')
    else:
        eleves = Eleve.objects.filter(classe="3ème").order_by('nom','prenoms')
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""

    return render(request, 'listes_classes/3ème.html', {
        'eleves': eleves,
        "school_name": school_name,
        'classe': "3ème",
        'annee_academique': annee_academique  # Passer l'année sélectionnée pour pré-remplir le champ dans le formulaire
    })

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Eleve, Note, Login
def inserer_notes_classe_view(request, classe, annee_academique):
    eleves = list(Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by("nom", "prenoms"))
    user = Login.objects.first()
    school_name = user.school_name if user else ""

    matieres = [
        "Lecture", "Communication-Ecrite", "Histoire-Géographie",
        "SVT", "PCT", "Mathématiques", "Anglais",
        "EPS", "Espagnol", "Conduite", "Informatique"
    ]
    type_notes = ["interro1", "interro2", "interro3", "devoir1", "devoir2"]

    # Charger toutes les notes en une seule fois
    all_notes = Note.objects.filter(
        eleve__in=eleves,
        annee_academique=annee_academique
    ).select_related("eleve")

    notes_existantes = {}
    for eleve in eleves:
        notes_e = [n for n in all_notes if n.eleve_id == eleve.id]
        notes_existantes[eleve.id] = {
            f"{n.matiere}_{n.type_note}_{n.trimestre}": n.valeur for n in notes_e
        }

    if request.method == "POST":
        action = request.POST.get("action")
        matiere = request.POST.get("matiere")
        type_note = request.POST.get("type_note")
        trimestre = int(request.POST.get("trimestre", 1))

        if action == "sauvegarder":
            updates, creations = [], []
            for eleve in eleves:
                valeur = request.POST.get(f"note_{eleve.id}")
                if valeur:
                    try:
                        valeur = float(valeur)
                        if not (0 <= valeur <= 20):
                            raise ValueError("La note doit être comprise entre 0 et 20.")

                        note_obj = next(
                            (n for n in all_notes if n.eleve_id == eleve.id and n.matiere == matiere and n.type_note == type_note and n.trimestre == trimestre),
                            None
                        )
                        if note_obj:
                            note_obj.valeur = valeur
                            updates.append(note_obj)
                        else:
                            creations.append(Note(
                                eleve=eleve,
                                matiere=matiere,
                                type_note=type_note,
                                valeur=valeur,
                                trimestre=trimestre,
                                annee_academique=annee_academique
                            ))
                    except ValueError:
                        messages.error(request, f"Valeur invalide pour {eleve.nom} {eleve.prenoms}")

            if updates:
                Note.objects.bulk_update(updates, ["valeur"])
            if creations:
                Note.objects.bulk_create(creations)

            messages.success(request, "Les notes ont été sauvegardées avec succès.")
            return redirect('inserer_notes_classe', classe=classe, annee_academique=annee_academique)

        elif action == "calculer":
            trimestre_notes = [n for n in all_notes if n.trimestre == trimestre]
            updates = []

            # Calcul par élève
            moyennes_eleves = []
            for eleve in eleves:
                notes = [n for n in trimestre_notes if n.eleve_id == eleve.id]
                matieres_status = {}

                for note in notes:
                    m = note.matiere
                    if m not in matieres_status:
                        matieres_status[m] = {
                            'interros': [], 'devoirs': [],
                            'moyenne_interros': 0,
                            'moyenne_devoirs': 0,
                            'moyenne_generale': None
                        }

                    if note.type_note in ['interro1', 'interro2', 'interro3']:
                        matieres_status[m]['interros'].append(note.valeur)
                    elif note.type_note in ['devoir1', 'devoir2']:
                        matieres_status[m]['devoirs'].append(note.valeur)

                # Calcul des moyennes
                for matiere_nom, status in matieres_status.items():
                    interros = status['interros']
                    devoirs = status['devoirs']

                    status['moyenne_interros'] = round(sum(interros)/len(interros), 2) if interros else 0
                    status['moyenne_devoirs'] = round(sum(devoirs)/len(devoirs), 2) if devoirs else 0

                    if not interros:
                        status['moyenne_generale'] = status['moyenne_devoirs']
                    elif len(devoirs) == 2:
                        status['moyenne_generale'] = round((sum(devoirs) + status['moyenne_interros']) / 3, 2)
                    elif len(devoirs) == 1:
                        status['moyenne_generale'] = round((devoirs[0] + status['moyenne_interros']) / 2, 2)

                    for note in notes:
                        if note.matiere == matiere_nom:
                            note.moyenne_interrogations = status['moyenne_interros']
                            note.moyenne_devoirs = status['moyenne_devoirs']
                            note.moyenne_generale = status['moyenne_generale']
                            updates.append(note)

                # Moyenne trimestrielle
                total_pondere, total_coeff = 0, 0
                for matiere, status in matieres_status.items():
                    if status['moyenne_generale'] is not None:
                        note_ref = next((n for n in notes if n.matiere == matiere), None)
                        coef = getattr(note_ref, "coefficient", 1) or 1
                        total_pondere += status['moyenne_generale'] * coef
                        total_coeff += coef

                moyenne_trimestrielle = total_pondere / total_coeff if total_coeff > 0 else 0

                for note in notes:
                    note.moyenne_trimestrielle = moyenne_trimestrielle
                    updates.append(note)

                moyennes_eleves.append((eleve, moyenne_trimestrielle))

            # Classement
            moyennes_eleves.sort(key=lambda x: x[1], reverse=True)
            for index, (eleve, _) in enumerate(moyennes_eleves):
                rang = index + 1
                for note in [n for n in trimestre_notes if n.eleve_id == eleve.id]:
                    note.rang = rang
                    updates.append(note)

            # Enregistrement en une seule fois
            if updates:
                Note.objects.bulk_update(
                    updates,
                    ["valeur", "moyenne_interrogations", "moyenne_devoirs",
                     "moyenne_generale", "moyenne_trimestrielle", "rang"]
                )

            messages.success(request, "Les moyennes et le classement ont été calculés avec succès.")
            return redirect('inserer_notes_classe', classe=classe, annee_academique=annee_academique)

    return render(request, "inserer_note.html", {
        "eleves": eleves,
        "classe": classe,
        "annee_academique": annee_academique,
        "school_name": school_name,
        "matieres": matieres,
        "type_notes": type_notes,
        "notes_existantes": notes_existantes
    })


# ------------------------- MODIFIER NOTE -----------------------------

def modifier_note(request, classe, annee_academique):
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by("nom", "prenoms")
    user = Login.objects.first()
    school_name = user.school_name if user else ""

    if request.method == "POST":
        matiere = request.POST.get("matiere")
        type_note = request.POST.get("type_note")
        trimestre = int(request.POST.get("trimestre", 1))
        action = request.POST.get("action")

        if action == "sauvegarder":
            for eleve in eleves:
                valeur = request.POST.get(f"note_{eleve.id}")
                if valeur:
                    try:
                        valeur = float(valeur)
                        if not (0 <= valeur <= 20):
                            raise ValueError("La note doit être comprise entre 0 et 20.")
                        note_existante = Note.objects.filter(
                            eleve=eleve,
                            matiere=matiere,
                            type_note=type_note,
                            trimestre=trimestre,
                            annee_academique=annee_academique
                        ).first()
                        if note_existante:
                            note_existante.valeur = valeur
                            note_existante.save()
                        else:
                            Note.objects.create(
                                eleve=eleve,
                                matiere=matiere,
                                type_note=type_note,
                                valeur=valeur,
                                trimestre=trimestre,
                                annee_academique=annee_academique
                            )
                    except ValueError:
                        messages.error(request, f"Valeur invalide pour {eleve.nom} {eleve.prenoms}")

            messages.success(request, "Les notes ont été modifiées avec succès.")
            return redirect('modifier_notes_classe', classe=classe, annee_academique=annee_academique)

        elif action == "calculer":
            for eleve in eleves:
                notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)
                matieres_status = {}

                for note in notes:
                    if note.matiere not in matieres_status:
                        matieres_status[note.matiere] = {
                            'interros': [], 'devoirs': [], 'moyenne_interros': 0,
                            'moyenne_devoirs': 0, 'moyenne_generale': None
                        }

                    if note.type_note in ['interro1','interro2','interro3']:
                        matieres_status[note.matiere]['interros'].append(note.valeur)
                    elif note.type_note in ['devoir1','devoir2']:
                        matieres_status[note.matiere]['devoirs'].append(note.valeur)

                for matiere_nom, status in matieres_status.items():
                    interros = status['interros']
                    devoirs = status['devoirs']

                    status['moyenne_interros'] = sum(interros)/len(interros) if interros else 0
                    status['moyenne_devoirs'] = sum(devoirs)/len(devoirs) if devoirs else 0

                    # ⚙️ Même règle que plus haut
                    if not interros:
                        status['moyenne_generale'] = status['moyenne_devoirs']
                    elif len(devoirs) == 2:
                        status['moyenne_generale'] = round((sum(devoirs) + status['moyenne_interros']) / 3, 2)
                    elif len(devoirs) == 1:
                        status['moyenne_generale'] = round((devoirs[0] + status['moyenne_interros']) / 2, 2)
                    else:
                        status['moyenne_generale'] = status['moyenne_interros']

                    for note in notes.filter(matiere=matiere_nom):
                        note.moyenne_interrogations = status['moyenne_interros']
                        note.moyenne_devoirs = status['moyenne_devoirs']
                        note.moyenne_generale = status['moyenne_generale']
                        note.save()

                total_pondere = 0
                total_coeff = 0
                for matiere, status in matieres_status.items():
                    if status['moyenne_generale'] is not None:
                        coefficient = notes.filter(matiere=matiere).first().coefficient if notes.filter(matiere=matiere).exists() else 1
                        total_pondere += status['moyenne_generale'] * coefficient
                        total_coeff += coefficient
                moyenne_trimestrielle = total_pondere / total_coeff if total_coeff > 0 else 0

                for note in notes:
                    note.moyenne_trimestrielle = moyenne_trimestrielle
                    note.save()

            eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
            moyennes_eleves = []
            for e in eleves_classe:
                notes_e = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee_academique)
                moyenne_e = notes_e.first().moyenne_trimestrielle if notes_e.exists() else 0
                moyennes_eleves.append((e, moyenne_e))
            moyennes_eleves.sort(key=lambda x: x[1], reverse=True)

            for index, (e, _) in enumerate(moyennes_eleves):
                rang = index + 1
                for note in Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee_academique):
                    note.rang = rang
                    note.save()

            messages.success(request, "Les moyennes ont été calculées avec succès.")
            return redirect('modifier_note', classe=classe, annee_academique=annee_academique)

    notes_existantes = {}
    for eleve in eleves:
        notes_eleves = Note.objects.filter(eleve=eleve, annee_academique=annee_academique)
        notes_existantes[eleve.id] = {
            f"{note.matiere}_{note.type_note}_{note.trimestre}": note.valeur
            for note in notes_eleves
        }

    return render(request, "modifier_note.html", {
        "eleves": eleves,
        "classe": classe,
        "annee_academique": annee_academique,
        "school_name": school_name,
        "notes_existantes": notes_existantes
    })


def supprimer_eleve(request, id_eleve):
    # Récupérer l'élève avec l'ID spécifié
    eleve = get_object_or_404(Eleve, id=id_eleve)
    
    # Supprimer les notes associées à cet élève
    eleve.note_set.all().delete()
    
    # Supprimer l'élève
    eleve.delete()
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""
     
    # Rediriger vers la page d'accueil ou une autre page
    return redirect(request.META['HTTP_REFERER'],{"school_name": school_name})  # Remplacez par l'URL de redirection souhaitée

from django.shortcuts import render
from .models import Eleve, Note, Login

def notes_eleve(request, eleve_id):
    # Récupérer l'élève
    eleve = Eleve.objects.get(id=eleve_id)

    # Récupérer le trimestre sélectionné (par défaut 1)
    trimestre = int(request.GET.get('trimestre', 1))

    # Récupérer l'année académique de l'élève
    annee_academique = eleve.annee_academique.strip()

    # Récupérer toutes les notes de l'élève pour le trimestre et l'année académique
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

    # Initialiser une structure pour stocker les notes par matière
    matieres_status = {}

    # Regroupement des notes par matière
    for n in notes:
        if n.matiere not in matieres_status:
            matieres_status[n.matiere] = {
                'interros': [],
                'devoirs': [],
                'moyenne_interros': 0,
                'moyenne_devoirs': 0,
                'moyenne_generale': None,
            }

        if n.type_note in ['interro1', 'interro2', 'interro3']:
            matieres_status[n.matiere]['interros'].append(n.valeur)
        elif n.type_note in ['devoir1', 'devoir2']:
            matieres_status[n.matiere]['devoirs'].append(n.valeur)

    # Calcul des moyennes par matière (même logique que inserer_notes_classe_view)
    for matiere, status in matieres_status.items():
        interros = status['interros']
        devoirs = status['devoirs']

        # Moyenne d'interros (None si aucune interro)
        moy_interro = sum(interros) / len(interros) if interros else None
        status['moyenne_interros'] = round(moy_interro, 2) if moy_interro is not None else 0

        # Moyenne des devoirs (0 si aucun devoir)
        status['moyenne_devoirs'] = round(sum(devoirs) / len(devoirs), 2) if devoirs else 0

        # Moyenne générale : uniquement si au moins un devoir
        if devoirs:
            total = 0
            compteur = 0
            if moy_interro is not None:
                total += moy_interro
                compteur += 1
            total += sum(devoirs)
            compteur += len(devoirs)
            status['moyenne_generale'] = round(total / compteur, 2)
        else:
            # Aucun devoir => pas de moyenne générale (None)
            status['moyenne_generale'] = None

        # Sauvegarder les moyennes calculées dans la base pour toutes les notes de la matière
        for note_obj in notes.filter(matiere=matiere):
            note_obj.moyenne_interrogations = status['moyenne_interros']
            note_obj.moyenne_devoirs = status['moyenne_devoirs']
            note_obj.moyenne_generale = status['moyenne_generale']
            note_obj.save()

    # Calcul de la moyenne trimestrielle pondérée pour l'élève
    total_notes_ponderees = 0
    total_coefficients = 0

    # Si la classe est 4ème ou 3ème, utiliser les coefficients stockés sur les notes (ou fallback = 1)
    if eleve.classe in ['4ème', '3ème']:
        for matiere, status in matieres_status.items():
            if status['moyenne_generale'] is not None:
                # Récupérer une note pour obtenir le coefficient si disponible
                note_ref = Note.objects.filter(eleve=eleve, matiere=matiere, trimestre=trimestre, annee_academique=annee_academique).first()
                coef = note_ref.coefficient if note_ref and getattr(note_ref, 'coefficient', None) is not None else 1
                total_notes_ponderees += status['moyenne_generale'] * coef
                total_coefficients += coef
    else:
        # Même logique mais poids = 1 par matière (même que coefficient implicite)
        for matiere, status in matieres_status.items():
            if status['moyenne_generale'] is not None:
                total_notes_ponderees += status['moyenne_generale']
                total_coefficients += 1

    if total_coefficients > 0:
        moyenne_trimestrielle = round(total_notes_ponderees / total_coefficients, 2)
    else:
        moyenne_trimestrielle = 0

    # Sauvegarder la moyenne trimestrielle dans la base de données (toutes les notes de l'élève pour le trimestre)
    for note_obj in notes:
        note_obj.moyenne_trimestrielle = moyenne_trimestrielle
        note_obj.save()

    # Calcul du classement pour la classe (sur la base des moyennes trimestrielles sauvegardées)
    eleves_classe = Eleve.objects.filter(classe=eleve.classe, annee_academique=annee_academique)
    moyennes_eleves = []
    for e in eleves_classe:
        note_first = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee_academique).first()
        moyenne_e = note_first.moyenne_trimestrielle if note_first and note_first.moyenne_trimestrielle is not None else 0
        moyennes_eleves.append((e, moyenne_e))

    # Trier décroissant et attribuer rangs
    moyennes_eleves.sort(key=lambda x: x[1], reverse=True)
    for index, (e, _) in enumerate(moyennes_eleves):
        rang = index + 1
        notes_e = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee_academique)
        for note_obj in notes_e:
            note_obj.rang = rang
            note_obj.save()

    # Récupérer le rang de l'élève courant
    rang = next((i + 1 for i, (e, m) in enumerate(moyennes_eleves) if e == eleve), 0)

    # Récupérer le nom de l'école
    user = Login.objects.first()
    school_name = user.school_name if user else ""

    # Préparer le contexte pour affichage (matieres_status contient les moyennes par matière)
    context = {
        "eleve": eleve,
        "classe": eleve.classe,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "rang": rang,
        "matieres_status": matieres_status,
        "trimestre": trimestre,
        "school_name": school_name
    }
    return render(request, "notes_eleve.html", context)

# Définir une fonction qui retourne le coefficient en fonction de la classe et de la matière
def get_coefficient(classe, matiere):
    if classe in ['4ème', '3ème']:
        if matiere == 'Mathématiques':
            return 3
        elif matiere in ['EPS', 'Conduite','Informatique']:
            return 1
        else:
            return 2
    else:
        # Coefficient par défaut pour les autres classes
        return 1  # Ou un autre coefficient par défaut que tu préfères


from django.shortcuts import render
from .models import Eleve, Note, Login

def get_coefficient(classe, matiere):
    """
    Fonction pour déterminer le coefficient d'une matière en fonction de la classe.
    """
    if classe in ['4ème', '3ème']:
        if matiere == 'Mathématiques':
            return 3
        elif matiere in ['EPS', 'Informatique', 'Conduite']:
            return 1
        else:
            return 2
    elif classe in ['6ème', '5ème']:
        return 1
    else:
        return 0

def get_appreciation(moyenne):
    """
    Retourne l'appréciation en fonction de la moyenne.
    """
    if moyenne is None:
        return ""
    elif moyenne < 8:
        return "Faible"
    elif moyenne < 10:
        return "Insuffisant"
    elif moyenne < 12:
        return "Passable"
    elif moyenne < 14:
        return "Assez-bien"
    elif moyenne < 16:
        return "Bien"
    else:
        return "Très-bien"

def bulletin_trimestre1(request, classe, eleve_id):
    eleve = Eleve.objects.get(id=eleve_id)
    trimestre = '1'
    annee_academique = eleve.annee_academique.strip()
    total_eleve = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).count()

    # Liste des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Initialisation
    matieres_status = {
        matiere: {
            'interros': [],
            'devoirs': [],
            'moyenne_interros': 0,
            'moyenne_devoirs': 0,
            'moyenne_generale': None,
            'coef': 0,
            'moyenne_coef': 0,
            'rang': 0,
            'appreciations': ''
        }
        for matiere in order_of_subjects
    }

    # Récupérer toutes les notes de l'élève
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

    # Remplissage interros/devoirs
    for note in notes:
        if note.matiere in matieres_status:
            if note.type_note in ['interro1', 'interro2', 'interro3']:
                matieres_status[note.matiere]['interros'].append(note.valeur)
            elif note.type_note in ['devoir1', 'devoir2']:
                matieres_status[note.matiere]['devoirs'].append(note.valeur)

    # Calcul des moyennes par matière
    for matiere, status in matieres_status.items():
        interros = status['interros']
        devoirs = status['devoirs']

        status['moyenne_interros'] = round(sum(interros) / len(interros), 2) if interros else 0
        status['moyenne_devoirs'] = round(sum(devoirs) / len(devoirs), 2) if devoirs else 0

        # Moyenne générale
        if not interros and devoirs:
            status['moyenne_generale'] = status['moyenne_devoirs']
        elif interros and len(devoirs) >= 1:
            status['moyenne_generale'] = round((status['moyenne_interros'] + sum(devoirs)) / (len(devoirs)+1), 2)
        else:
            status['moyenne_generale'] = None

        # Coefficient et moyenne pondérée
        status['coef'] = get_coefficient(classe, matiere)
        status['moyenne_coef'] = (
            status['moyenne_generale'] * status['coef']
            if status['moyenne_generale'] is not None else 0
        )

        # Appréciation
        status['appreciations'] = get_appreciation(status['moyenne_generale'])

    # Rang par matière dans la classe
    for matiere, status in matieres_status.items():
        eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
        moyennes_matiere = []

        for e in eleves_classe:
            notes_matiere = Note.objects.filter(eleve=e, matiere=matiere, trimestre=trimestre)
            interros = notes_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = notes_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)
            
            if not interros and devoirs:
                moyenne_generale = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne_generale = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            elif interros:
                moyenne_generale = sum(interros)/len(interros)
            else:
                moyenne_generale = 0

            moyennes_matiere.append((e, moyenne_generale))

        moyennes_matiere.sort(key=lambda x: x[1], reverse=True)
        for index, (e, moy) in enumerate(moyennes_matiere):
            if e == eleve:
                status['rang'] = index + 1
                break

    # Moyenne trimestrielle de l'élève (en prenant seulement les matières avec moyenne)
    total_notes_ponderees = 0
    total_coefficients = 0
    for status in matieres_status.values():
        if status['moyenne_generale'] is not None:
            total_notes_ponderees += status['moyenne_generale'] * status['coef']
            total_coefficients += status['coef']
    moyenne_trimestrielle = total_notes_ponderees / total_coefficients if total_coefficients > 0 else 0

    # Moyenne max et min de la classe
    eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
    moyennes_classe = []
    for e in eleves_classe:
        total_pondere = 0
        total_coef = 0
        notes_e = Note.objects.filter(eleve=e, trimestre=trimestre)
        for matiere in order_of_subjects:
            n_matiere = notes_e.filter(matiere=matiere)
            interros = n_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = n_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)

            if not interros and devoirs:
                moyenne = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            else:
                moyenne = None

            coef = get_coefficient(classe, matiere)
            if moyenne is not None:
                total_pondere += moyenne * coef
                total_coef += coef

        moyenne_eleve = total_pondere / total_coef if total_coef > 0 else 0
        moyennes_classe.append((e, moyenne_eleve))

    moyennes_classe.sort(key=lambda x: x[1], reverse=True)
    rang_trimestriel = next((i+1 for i,(e,m) in enumerate(moyennes_classe) if e==eleve), 0)

    # Données pour le template
    user = Login.objects.first()
    context = {
        "eleve": eleve,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "matieres_status": matieres_status,
        "moyenne_max": moyennes_classe[0][1] if moyennes_classe else 0,
        "moyenne_min": moyennes_classe[-1][1] if moyennes_classe else 0,
        "trimestre": trimestre,
        "classe_eleve": eleve.classe,
        "school_name": user.school_name if user else "",
        "email": user.email if user else "unknown",
        "numero": user.numero if user else "unknown",
        "name": user.name if user else "unknown",
        "total_eleve": total_eleve,
        "profile_image": user.profile_image.url if user and user.profile_image else None,
        "rang_trimestriel": rang_trimestriel,
    }

    return render(request, 'bulletin/trimestre1.html', context)

def bulletin_trimestre2(request, classe, eleve_id):
    eleve = Eleve.objects.get(id=eleve_id)
    trimestre = '2'
    annee_academique = eleve.annee_academique.strip()
    total_eleve = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).count()

    # Liste des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Initialisation
    matieres_status = {
        matiere: {
            'interros': [],
            'devoirs': [],
            'moyenne_interros': 0,
            'moyenne_devoirs': 0,
            'moyenne_generale': None,
            'coef': 0,
            'moyenne_coef': 0,
            'rang': 0,
            'appreciations': ''
        }
        for matiere in order_of_subjects
    }

    # Récupérer toutes les notes de l'élève
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

    # Remplissage interros/devoirs
    for note in notes:
        if note.matiere in matieres_status:
            if note.type_note in ['interro1', 'interro2', 'interro3']:
                matieres_status[note.matiere]['interros'].append(note.valeur)
            elif note.type_note in ['devoir1', 'devoir2']:
                matieres_status[note.matiere]['devoirs'].append(note.valeur)

    # Calcul des moyennes par matière
    for matiere, status in matieres_status.items():
        interros = status['interros']
        devoirs = status['devoirs']

        status['moyenne_interros'] = round(sum(interros) / len(interros), 2) if interros else 0
        status['moyenne_devoirs'] = round(sum(devoirs) / len(devoirs), 2) if devoirs else 0

        # Moyenne générale
        if not interros and devoirs:
            status['moyenne_generale'] = status['moyenne_devoirs']
        elif interros and len(devoirs) >= 1:
            status['moyenne_generale'] = round((status['moyenne_interros'] + sum(devoirs)) / (len(devoirs)+1), 2)
        else:
            status['moyenne_generale'] = None

        # Coefficient et moyenne pondérée
        status['coef'] = get_coefficient(classe, matiere)
        status['moyenne_coef'] = (
            status['moyenne_generale'] * status['coef']
            if status['moyenne_generale'] is not None else 0
        )

        # Appréciation
        status['appreciations'] = get_appreciation(status['moyenne_generale'])

    # Rang par matière dans la classe
    for matiere, status in matieres_status.items():
        eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
        moyennes_matiere = []

        for e in eleves_classe:
            notes_matiere = Note.objects.filter(eleve=e, matiere=matiere, trimestre=trimestre)
            interros = notes_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = notes_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)
            
            if not interros and devoirs:
                moyenne_generale = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne_generale = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            elif interros:
                moyenne_generale = sum(interros)/len(interros)
            else:
                moyenne_generale = 0

            moyennes_matiere.append((e, moyenne_generale))

        moyennes_matiere.sort(key=lambda x: x[1], reverse=True)
        for index, (e, moy) in enumerate(moyennes_matiere):
            if e == eleve:
                status['rang'] = index + 1
                break

    # Moyenne trimestrielle de l'élève (en prenant seulement les matières avec moyenne)
    total_notes_ponderees = 0
    total_coefficients = 0
    for status in matieres_status.values():
        if status['moyenne_generale'] is not None:
            total_notes_ponderees += status['moyenne_generale'] * status['coef']
            total_coefficients += status['coef']
    moyenne_trimestrielle = total_notes_ponderees / total_coefficients if total_coefficients > 0 else 0

    # Moyenne max et min de la classe
    eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
    moyennes_classe = []
    for e in eleves_classe:
        total_pondere = 0
        total_coef = 0
        notes_e = Note.objects.filter(eleve=e, trimestre=trimestre)
        for matiere in order_of_subjects:
            n_matiere = notes_e.filter(matiere=matiere)
            interros = n_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = n_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)

            if not interros and devoirs:
                moyenne = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            else:
                moyenne = None

            coef = get_coefficient(classe, matiere)
            if moyenne is not None:
                total_pondere += moyenne * coef
                total_coef += coef

        moyenne_eleve = total_pondere / total_coef if total_coef > 0 else 0
        moyennes_classe.append((e, moyenne_eleve))

    moyennes_classe.sort(key=lambda x: x[1], reverse=True)
    rang_trimestriel = next((i+1 for i,(e,m) in enumerate(moyennes_classe) if e==eleve), 0)

    # Données pour le template
    user = Login.objects.first()
    context = {
        "eleve": eleve,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "matieres_status": matieres_status,
        "moyenne_max": moyennes_classe[0][1] if moyennes_classe else 0,
        "moyenne_min": moyennes_classe[-1][1] if moyennes_classe else 0,
        "trimestre": trimestre,
        "classe_eleve": eleve.classe,
        "school_name": user.school_name if user else "",
        "email": user.email if user else "unknown",
        "numero": user.numero if user else "unknown",
        "name": user.name if user else "unknown",
        "total_eleve": total_eleve,
        "profile_image": user.profile_image.url if user and user.profile_image else None,
        "rang_trimestriel": rang_trimestriel,
    }

    return render(request, 'bulletin/trimestre2.html', context)

def bulletin_trimestre3(request, classe, eleve_id):
    eleve = Eleve.objects.get(id=eleve_id)
    trimestre = '3'
    annee_academique = eleve.annee_academique.strip()
    total_eleve = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).count()

    # Liste des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Initialisation
    matieres_status = {
        matiere: {
            'interros': [],
            'devoirs': [],
            'moyenne_interros': 0,
            'moyenne_devoirs': 0,
            'moyenne_generale': None,
            'coef': 0,
            'moyenne_coef': 0,
            'rang': 0,
            'appreciations': ''
        }
        for matiere in order_of_subjects
    }

    # Récupérer toutes les notes de l'élève
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

    # Remplissage interros/devoirs
    for note in notes:
        if note.matiere in matieres_status:
            if note.type_note in ['interro1', 'interro2', 'interro3']:
                matieres_status[note.matiere]['interros'].append(note.valeur)
            elif note.type_note in ['devoir1', 'devoir2']:
                matieres_status[note.matiere]['devoirs'].append(note.valeur)

    # Calcul des moyennes par matière
    for matiere, status in matieres_status.items():
        interros = status['interros']
        devoirs = status['devoirs']

        status['moyenne_interros'] = round(sum(interros) / len(interros), 2) if interros else 0
        status['moyenne_devoirs'] = round(sum(devoirs) / len(devoirs), 2) if devoirs else 0

        # Moyenne générale
        if not interros and devoirs:
            status['moyenne_generale'] = status['moyenne_devoirs']
        elif interros and len(devoirs) >= 1:
            status['moyenne_generale'] = round((status['moyenne_interros'] + sum(devoirs)) / (len(devoirs)+1), 2)
        else:
            status['moyenne_generale'] = None

        # Coefficient et moyenne pondérée
        status['coef'] = get_coefficient(classe, matiere)
        status['moyenne_coef'] = (
            status['moyenne_generale'] * status['coef']
            if status['moyenne_generale'] is not None else 0
        )

        # Appréciation
        status['appreciations'] = get_appreciation(status['moyenne_generale'])

    # Rang par matière dans la classe
    for matiere, status in matieres_status.items():
        eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
        moyennes_matiere = []

        for e in eleves_classe:
            notes_matiere = Note.objects.filter(eleve=e, matiere=matiere, trimestre=trimestre)
            interros = notes_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = notes_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)
            
            if not interros and devoirs:
                moyenne_generale = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne_generale = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            elif interros:
                moyenne_generale = sum(interros)/len(interros)
            else:
                moyenne_generale = 0

            moyennes_matiere.append((e, moyenne_generale))

        moyennes_matiere.sort(key=lambda x: x[1], reverse=True)
        for index, (e, moy) in enumerate(moyennes_matiere):
            if e == eleve:
                status['rang'] = index + 1
                break

    # Moyenne trimestrielle de l'élève (en prenant seulement les matières avec moyenne)
    total_notes_ponderees = 0
    total_coefficients = 0
    for status in matieres_status.values():
        if status['moyenne_generale'] is not None:
            total_notes_ponderees += status['moyenne_generale'] * status['coef']
            total_coefficients += status['coef']
    moyenne_trimestrielle = total_notes_ponderees / total_coefficients if total_coefficients > 0 else 0

    # Moyenne max et min de la classe
    eleves_classe = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
    moyennes_classe = []
    for e in eleves_classe:
        total_pondere = 0
        total_coef = 0
        notes_e = Note.objects.filter(eleve=e, trimestre=trimestre)
        for matiere in order_of_subjects:
            n_matiere = notes_e.filter(matiere=matiere)
            interros = n_matiere.filter(type_note__in=['interro1','interro2','interro3']).values_list('valeur', flat=True)
            devoirs = n_matiere.filter(type_note__in=['devoir1','devoir2']).values_list('valeur', flat=True)

            if not interros and devoirs:
                moyenne = sum(devoirs)/len(devoirs)
            elif interros and len(devoirs) >= 1:
                moyenne = (sum(interros)/len(interros) + sum(devoirs)) / (len(devoirs)+1)
            else:
                moyenne = None

            coef = get_coefficient(classe, matiere)
            if moyenne is not None:
                total_pondere += moyenne * coef
                total_coef += coef

        moyenne_eleve = total_pondere / total_coef if total_coef > 0 else 0
        moyennes_classe.append((e, moyenne_eleve))

    moyennes_classe.sort(key=lambda x: x[1], reverse=True)
    rang_trimestriel = next((i+1 for i,(e,m) in enumerate(moyennes_classe) if e==eleve), 0)

    # Données pour le template
    user = Login.objects.first()
    context = {
        "eleve": eleve,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "matieres_status": matieres_status,
        "moyenne_max": moyennes_classe[0][1] if moyennes_classe else 0,
        "moyenne_min": moyennes_classe[-1][1] if moyennes_classe else 0,
        "trimestre": trimestre,
        "classe_eleve": eleve.classe,
        "school_name": user.school_name if user else "",
        "email": user.email if user else "unknown",
        "numero": user.numero if user else "unknown",
        "name": user.name if user else "unknown",
        "total_eleve": total_eleve,
        "profile_image": user.profile_image.url if user and user.profile_image else None,
        "rang_trimestriel": rang_trimestriel,
    }

    return render(request, 'bulletin/trimestre3.html', context)


from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Eleve, Note, Login

def affichemoy_trimestre1(request, classe, annee_academique):
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom','prenoms')
    trimestre = request.GET.get('trimestre', '1')

    resultats_eleves = []
    moyennes_trimestrielles = []

    # Ordre des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialisation
        matieres_status = {matiere: {'interros': [], 'devoirs': [], 'moyenne_interros': '', 'moyenne_devoirs': '', 'moyenne_generale': ''} for matiere in order_of_subjects}

        # Regrouper les notes par matière
        for note in notes:
            if note.matiere in matieres_status:
                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    matieres_status[note.matiere]['interros'].append(note.valeur)
                elif note.type_note in ['devoir1', 'devoir2']:
                    matieres_status[note.matiere]['devoirs'].append(note.valeur)

        # Calculer les moyennes réelles
        for matiere, status in matieres_status.items():
            interros = status['interros']
            devoirs = status['devoirs']

            status['moyenne_interros'] = round(sum(interros)/len(interros), 2) if interros else ''
            status['moyenne_devoirs'] = round(sum(devoirs)/len(devoirs), 2) if devoirs else ''
            # ⚙️ Si pas de moyenne d’interro, la moyenne générale = moyenne des devoirs
            if not interros:
                status['moyenne_generale'] = status['moyenne_devoirs']
            elif len(devoirs) == 2:
                status['moyenne_generale'] = round((sum(devoirs) + status['moyenne_interros']) / 3, 2)
            elif len(devoirs) == 1:
                status['moyenne_generale'] = round((devoirs[0] + status['moyenne_interros']) / 2, 2)
            else:
                status['moyenne_generale'] = 0
        # Moyenne trimestrielle
        moyenne_trimestrielle = notes.first().moyenne_trimestrielle if notes.exists() and notes.first().moyenne_trimestrielle is not None else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: -float(x['moyenne_trimestrielle']))
    for idx, result in enumerate(resultats_eleves):
        result['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    # Statistiques
    nb_moyenne_sup10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] >= 10)
    nb_moyenne_inf10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] < 10)
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "nb_moyenne_sup10": nb_moyenne_sup10,
        "nb_moyenne_inf10": nb_moyenne_inf10,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre_1.html', context)


def affichemoy_trimestre2(request, classe, annee_academique):
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom','prenoms')
    trimestre = request.GET.get('trimestre', '2')

    resultats_eleves = []
    moyennes_trimestrielles = []

    # Ordre des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialisation
        matieres_status = {matiere: {'interros': [], 'devoirs': [], 'moyenne_interros': '', 'moyenne_devoirs': '', 'moyenne_generale': ''} for matiere in order_of_subjects}

        # Regrouper les notes par matière
        for note in notes:
            if note.matiere in matieres_status:
                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    matieres_status[note.matiere]['interros'].append(note.valeur)
                elif note.type_note in ['devoir1', 'devoir2']:
                    matieres_status[note.matiere]['devoirs'].append(note.valeur)

        # Calculer les moyennes réelles
        for matiere, status in matieres_status.items():
            interros = status['interros']
            devoirs = status['devoirs']

            status['moyenne_interros'] = round(sum(interros)/len(interros), 2) if interros else ''
            status['moyenne_devoirs'] = round(sum(devoirs)/len(devoirs), 2) if devoirs else ''
            if interros or devoirs:
                total = interros + devoirs
                status['moyenne_generale'] = round(sum(total)/len(total), 2)
            else:
                status['moyenne_generale'] = ''

        # Moyenne trimestrielle
        moyenne_trimestrielle = notes.first().moyenne_trimestrielle if notes.exists() and notes.first().moyenne_trimestrielle is not None else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: -float(x['moyenne_trimestrielle']))
    for idx, result in enumerate(resultats_eleves):
        result['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    # Statistiques
    nb_moyenne_sup10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] >= 10)
    nb_moyenne_inf10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] < 10)
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "nb_moyenne_sup10": nb_moyenne_sup10,
        "nb_moyenne_inf10": nb_moyenne_inf10,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre 2.html', context)


def affichemoy_trimestre3(request, classe, annee_academique):
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom','prenoms')
    trimestre = request.GET.get('trimestre', '3')

    resultats_eleves = []
    moyennes_trimestrielles = []

    # Ordre des matières
    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialisation
        matieres_status = {matiere: {'interros': [], 'devoirs': [], 'moyenne_interros': '', 'moyenne_devoirs': '', 'moyenne_generale': ''} for matiere in order_of_subjects}

        # Regrouper les notes par matière
        for note in notes:
            if note.matiere in matieres_status:
                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    matieres_status[note.matiere]['interros'].append(note.valeur)
                elif note.type_note in ['devoir1', 'devoir2']:
                    matieres_status[note.matiere]['devoirs'].append(note.valeur)

        # Calculer les moyennes réelles
        for matiere, status in matieres_status.items():
            interros = status['interros']
            devoirs = status['devoirs']

            status['moyenne_interros'] = round(sum(interros)/len(interros), 2) if interros else ''
            status['moyenne_devoirs'] = round(sum(devoirs)/len(devoirs), 2) if devoirs else ''
            if interros or devoirs:
                total = interros + devoirs
                status['moyenne_generale'] = round(sum(total)/len(total), 2)
            else:
                status['moyenne_generale'] = ''

        # Moyenne trimestrielle
        moyenne_trimestrielle = notes.first().moyenne_trimestrielle if notes.exists() and notes.first().moyenne_trimestrielle is not None else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: -float(x['moyenne_trimestrielle']))
    for idx, result in enumerate(resultats_eleves):
        result['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    # Statistiques
    nb_moyenne_sup10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] >= 10)
    nb_moyenne_inf10 = sum(1 for r in resultats_eleves if r['moyenne_trimestrielle'] < 10)
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "nb_moyenne_sup10": nb_moyenne_sup10,
        "nb_moyenne_inf10": nb_moyenne_inf10,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre 3.html', context)

def affichemoyexcel_trimestre1(request, classe, annee_academique):
    annee_academique = annee_academique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom', 'prenoms')
    trimestre = request.GET.get('trimestre', '1')

    resultats_eleves = []
    moyennes_trimestrielles = []

    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Coefficients par matière
    coefficients = {
        'Communication-Ecrite': 2,
        'Lecture': 2,
        'Histoire-Géographie': 2,
        'Mathématiques': 3,
        'PCT': 2,
        'SVT': 2,
        'Anglais': 2,
        'Espagnol': 2,
        'Informatique': 1,
        'EPS': 1,
        'Conduite': 1,
    }

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialiser les données de chaque matière
        matieres_status = {
            matiere: {
                'moyenne_interros': '',
                'devoir1': '',
                'devoir2': '',
                'moyenne_matiere': '',
                'mcoef': ''
            } for matiere in order_of_subjects
        }

        total_points = 0
        total_coeffs = 0

        # Répartir les notes dans leurs cases
        for note in notes:
            if note.matiere in matieres_status:
                d = matieres_status[note.matiere]

                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    # On met toutes les interros ensemble (calcul exact fait plus bas)
                    if d['moyenne_interros'] == '':
                        d['moyenne_interros'] = [note.valeur]
                    else:
                        d['moyenne_interros'].append(note.valeur)

                elif note.type_note == "devoir1":
                    d['devoir1'] = note.valeur
                elif note.type_note == "devoir2":
                    d['devoir2'] = note.valeur

        # Calcul des moyennes par matière (même logique que affichemoy_trimestre1)
        for matiere, d in matieres_status.items():

            # Interros
            if isinstance(d['moyenne_interros'], list):
                interros = d['moyenne_interros']
            else:
                interros = []

            devoirs = []
            if d['devoir1'] not in ['', None]:
                devoirs.append(float(d['devoir1']))
            if d['devoir2'] not in ['', None]:
                devoirs.append(float(d['devoir2']))

            # Moyenne interros
            moyenne_interros = round(sum(interros) / len(interros), 2) if interros else ''

            # Moyenne devoirs
            moyenne_devoirs = round(sum(devoirs) / len(devoirs), 2) if devoirs else ''

            # Moyenne matière (exactement comme affichemoy_trimestre1)
            if not interros:
                moyenne_matiere = moyenne_devoirs
            elif len(devoirs) == 2:
                moyenne_matiere = round((sum(devoirs) + moyenne_interros) / 3, 2)
            elif len(devoirs) == 1:
                moyenne_matiere = round((devoirs[0] + moyenne_interros) / 2, 2)
            else:
                moyenne_matiere = ''

            d['moyenne_interros'] = moyenne_interros
            d['moyenne_matiere'] = moyenne_matiere

            # Application du coefficient (inchangé)
            if moyenne_matiere not in ['', None]:
                coeff = coefficients.get(matiere, 1) if classe in ['4ème', '3ème'] else 1
                d['mcoef'] = round(moyenne_matiere * coeff, 2)

                total_points += d['mcoef']
                total_coeffs += coeff
            else:
                d['mcoef'] = ''

        # Moyenne trimestrielle calculée ici (comme avant)
        moyenne_trimestrielle = round(total_points / total_coeffs, 2) if total_coeffs > 0 else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: x['moyenne_trimestrielle'], reverse=True)
    for idx, res in enumerate(resultats_eleves):
        res['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistiques
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre1_excel.html', context)

from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Eleve, Note, Login

def affichemoyexcel_trimestre2(request, classe, annee_academique):
    annee_academique = annee_academique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom', 'prenoms')
    trimestre = request.GET.get('trimestre', '2')

    resultats_eleves = []
    moyennes_trimestrielles = []

    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Coefficients par matière
    coefficients = {
        'Communication-Ecrite': 2,
        'Lecture': 2,
        'Histoire-Géographie': 2,
        'Mathématiques': 3,
        'PCT': 2,
        'SVT': 2,
        'Anglais': 2,
        'Espagnol': 2,
        'Informatique': 1,
        'EPS': 1,
        'Conduite': 1,
    }

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialiser les données de chaque matière
        matieres_status = {
            matiere: {
                'moyenne_interros': '',
                'devoir1': '',
                'devoir2': '',
                'moyenne_matiere': '',
                'mcoef': ''
            } for matiere in order_of_subjects
        }

        total_points = 0
        total_coeffs = 0

        # Répartir les notes dans leurs cases
        for note in notes:
            if note.matiere in matieres_status:
                d = matieres_status[note.matiere]

                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    # On met toutes les interros ensemble (calcul exact fait plus bas)
                    if d['moyenne_interros'] == '':
                        d['moyenne_interros'] = [note.valeur]
                    else:
                        d['moyenne_interros'].append(note.valeur)

                elif note.type_note == "devoir1":
                    d['devoir1'] = note.valeur
                elif note.type_note == "devoir2":
                    d['devoir2'] = note.valeur

        # Calcul des moyennes par matière (même logique que affichemoy_trimestre1)
        for matiere, d in matieres_status.items():

            # Interros
            if isinstance(d['moyenne_interros'], list):
                interros = d['moyenne_interros']
            else:
                interros = []

            devoirs = []
            if d['devoir1'] not in ['', None]:
                devoirs.append(float(d['devoir1']))
            if d['devoir2'] not in ['', None]:
                devoirs.append(float(d['devoir2']))

            # Moyenne interros
            moyenne_interros = round(sum(interros) / len(interros), 2) if interros else ''

            # Moyenne devoirs
            moyenne_devoirs = round(sum(devoirs) / len(devoirs), 2) if devoirs else ''

            # Moyenne matière (exactement comme affichemoy_trimestre1)
            if not interros:
                moyenne_matiere = moyenne_devoirs
            elif len(devoirs) == 2:
                moyenne_matiere = round((sum(devoirs) + moyenne_interros) / 3, 2)
            elif len(devoirs) == 1:
                moyenne_matiere = round((devoirs[0] + moyenne_interros) / 2, 2)
            else:
                moyenne_matiere = ''

            d['moyenne_interros'] = moyenne_interros
            d['moyenne_matiere'] = moyenne_matiere

            # Application du coefficient (inchangé)
            if moyenne_matiere not in ['', None]:
                coeff = coefficients.get(matiere, 1) if classe in ['4ème', '3ème'] else 1
                d['mcoef'] = round(moyenne_matiere * coeff, 2)

                total_points += d['mcoef']
                total_coeffs += coeff
            else:
                d['mcoef'] = ''

        # Moyenne trimestrielle calculée ici (comme avant)
        moyenne_trimestrielle = round(total_points / total_coeffs, 2) if total_coeffs > 0 else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: x['moyenne_trimestrielle'], reverse=True)
    for idx, res in enumerate(resultats_eleves):
        res['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistiques
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre2_excel.html', context)



def affichemoyexcel_trimestre3(request, classe, annee_academique):
    annee_academique = annee_academique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom', 'prenoms')
    trimestre = request.GET.get('trimestre', '3')

    resultats_eleves = []
    moyennes_trimestrielles = []

    order_of_subjects = [
        'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
        'PCT', 'SVT', 'Anglais', 'Informatique', 'EPS', 'Conduite'
    ]
    if classe not in ['6ème', '5ème']:
        order_of_subjects.insert(6, 'Espagnol')

    # Coefficients par matière
    coefficients = {
        'Communication-Ecrite': 2,
        'Lecture': 2,
        'Histoire-Géographie': 2,
        'Mathématiques': 3,
        'PCT': 2,
        'SVT': 2,
        'Anglais': 2,
        'Espagnol': 2,
        'Informatique': 1,
        'EPS': 1,
        'Conduite': 1,
    }

    for eleve in eleves:
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        # Initialiser les données de chaque matière
        matieres_status = {
            matiere: {
                'moyenne_interros': '',
                'devoir1': '',
                'devoir2': '',
                'moyenne_matiere': '',
                'mcoef': ''
            } for matiere in order_of_subjects
        }

        total_points = 0
        total_coeffs = 0

        # Répartir les notes dans leurs cases
        for note in notes:
            if note.matiere in matieres_status:
                d = matieres_status[note.matiere]

                if note.type_note in ['interro1', 'interro2', 'interro3']:
                    # On met toutes les interros ensemble (calcul exact fait plus bas)
                    if d['moyenne_interros'] == '':
                        d['moyenne_interros'] = [note.valeur]
                    else:
                        d['moyenne_interros'].append(note.valeur)

                elif note.type_note == "devoir1":
                    d['devoir1'] = note.valeur
                elif note.type_note == "devoir2":
                    d['devoir2'] = note.valeur

        # Calcul des moyennes par matière (même logique que affichemoy_trimestre1)
        for matiere, d in matieres_status.items():

            # Interros
            if isinstance(d['moyenne_interros'], list):
                interros = d['moyenne_interros']
            else:
                interros = []

            devoirs = []
            if d['devoir1'] not in ['', None]:
                devoirs.append(float(d['devoir1']))
            if d['devoir2'] not in ['', None]:
                devoirs.append(float(d['devoir2']))

            # Moyenne interros
            moyenne_interros = round(sum(interros) / len(interros), 2) if interros else ''

            # Moyenne devoirs
            moyenne_devoirs = round(sum(devoirs) / len(devoirs), 2) if devoirs else ''

            # Moyenne matière (exactement comme affichemoy_trimestre1)
            if not interros:
                moyenne_matiere = moyenne_devoirs
            elif len(devoirs) == 2:
                moyenne_matiere = round((sum(devoirs) + moyenne_interros) / 3, 2)
            elif len(devoirs) == 1:
                moyenne_matiere = round((devoirs[0] + moyenne_interros) / 2, 2)
            else:
                moyenne_matiere = ''

            d['moyenne_interros'] = moyenne_interros
            d['moyenne_matiere'] = moyenne_matiere

            # Application du coefficient (inchangé)
            if moyenne_matiere not in ['', None]:
                coeff = coefficients.get(matiere, 1) if classe in ['4ème', '3ème'] else 1
                d['mcoef'] = round(moyenne_matiere * coeff, 2)

                total_points += d['mcoef']
                total_coeffs += coeff
            else:
                d['mcoef'] = ''

        # Moyenne trimestrielle calculée ici (comme avant)
        moyenne_trimestrielle = round(total_points / total_coeffs, 2) if total_coeffs > 0 else 0
        moyennes_trimestrielles.append(moyenne_trimestrielle)

        resultats_eleves.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': moyenne_trimestrielle,
            'rang': '-',
        })

    # Classement
    resultats_eleves.sort(key=lambda x: x['moyenne_trimestrielle'], reverse=True)
    for idx, res in enumerate(resultats_eleves):
        res['rang'] = idx + 1
    resultats_eleves.sort(key=lambda x: str(x['eleve'].nom))

    paginator = Paginator(resultats_eleves, 35)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistiques
    moyenne_max = max(moyennes_trimestrielles) if moyennes_trimestrielles else 0
    moyenne_min = min(moyennes_trimestrielles) if moyennes_trimestrielles else 0

    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    context = {
        "page_obj": page_obj,
        "is_last_page": page_obj.number == paginator.num_pages,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": moyenne_max,
        "moyenne_min": moyenne_min,
        "school_name": school_name,
        "classe": classe,
        "order_of_subjects": order_of_subjects,
        "profile_image": profile_image,
    }

    return render(request, 'moyenne/trimestre3_excel.html', context)

def liste_eleves(request, classe, annee_academique):
    # Filtrer les élèves par classe et année académique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom','prenoms')

    # Pagination : définir le nombre d'élèves par page (par exemple 40)
    paginator = Paginator(eleves, 50)
    
    # Récupérer le numéro de la page depuis les paramètres d'URL
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Ajouter un champ 'numéro_global' à chaque élève pour la pagination
    for index, eleve in enumerate(page_obj.object_list):
        eleve.numero_global = index + (page_obj.number - 1) * page_obj.paginator.per_page + 1

    # Récupérer la première ligne de la table Login pour le nom de l'école
    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None
    # Statistiques
    total_eleves = eleves.count()
    total_garcons = eleves.filter(sexe="M").count()
    total_filles = eleves.filter(sexe="F").count()

    # Passer la page paginée et les élèves avec leurs numéros globaux au template
    return render(request, 'listes_classes/liste_eleves.html', {
        'page_obj': page_obj,  # Passer la page paginée
        'eleves': page_obj.object_list,  # Passer les élèves avec les numéros globaux
        'classe': classe,
        'school_name': school_name,
        'annee_academique': annee_academique,
        'total_eleves': total_eleves,
        'total_garcons': total_garcons,
        'total_filles': total_filles,
        'profile_image': profile_image,
    })

def fiche_note(request, classe, annee_academique):
    # Filtrer les élèves par classe et année académique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by('nom','prenoms')

    # Pagination : définir le nombre d'élèves par page (par exemple 40)
    paginator = Paginator(eleves, 35)
    
    # Récupérer le numéro de la page depuis les paramètres d'URL
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Ajouter un champ 'numéro_global' à chaque élève pour la pagination
    for index, eleve in enumerate(page_obj.object_list):
        eleve.numero_global = index + (page_obj.number - 1) * page_obj.paginator.per_page + 1

    # Récupérer la première ligne de la table Login pour le nom de l'école
    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    # Passer la page paginée et les élèves avec leurs numéros globaux au template
    return render(request, 'fiche_note.html', {
        'page_obj': page_obj,  # Passer la page paginée
        'eleves': page_obj.object_list,  # Passer les élèves avec les numéros globaux
        'classe': classe,
        'school_name': school_name,
        'annee_academique': annee_academique,
        'profile_image': profile_image,
    })
def shutdown_server(request):
    """ Vue qui arrête le serveur Django """
    try:
        sys.exit()  # Arrête proprement le serveur
    except SystemExit:
        os._exit(0)  # Forcer la fermeture si nécessaire

    return HttpResponse("Serveur arrêté")

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Eleve, Note
from twilio.rest import Client
from django.conf import settings

def choisir_trimestre(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)

    if request.method == 'POST':
        trimestre = int(request.POST.get('trimestre'))
        return redirect('envoyer_sms_notes', eleve_id=eleve.id, trimestre=trimestre)

    return render(request, 'email.html', {"eleve": eleve})
    
def fiche_notes_detail(request, classe, annee_academique):
    eleves = Eleve.objects.filter(
        classe=classe,
        annee_academique=annee_academique
    ).order_by("nom", "prenoms")

    matieres = [
        "Lecture",
        "Communication-Ecrite",
        "Histoire-Géographie",
        "SVT",
        "PCT",
        "Mathématiques",
        "Anglais",
        "EPS",
        "Espagnol",
        "Conduite",
        "Informatique",
    ]

    matiere_choisie = request.GET.get("matiere", "")
    trimestre = int(request.GET.get("trimestre", 1))

    rows = []

    if matiere_choisie:
        moyennes_matiere = []

        for eleve in eleves:
            notes = Note.objects.filter(
                eleve=eleve,
                matiere=matiere_choisie,
                trimestre=trimestre,
                annee_academique=annee_academique
            )

            # 🔹 Récupération triée des interros
            i_notes = [
                notes.filter(type_note="interro1").first().valeur if notes.filter(type_note="interro1").exists() else None,
                notes.filter(type_note="interro2").first().valeur if notes.filter(type_note="interro2").exists() else None,
                notes.filter(type_note="interro3").first().valeur if notes.filter(type_note="interro3").exists() else None,
            ]

            # 🔹 Récupération triée des devoirs
            d_notes = [
                notes.filter(type_note="devoir1").first().valeur if notes.filter(type_note="devoir1").exists() else None,
                notes.filter(type_note="devoir2").first().valeur if notes.filter(type_note="devoir2").exists() else None,
            ]

            # 🔹 Filtrer valeurs valides
            i_valid = [n for n in i_notes if n is not None]
            d_valid = [n for n in d_notes if n is not None]

            # 🔹 Moyennes interros et devoirs
            moy_interro = round(sum(i_valid) / len(i_valid), 2) if i_valid else 0
            moy_dev = round(sum(d_valid) / len(d_valid), 2) if d_valid else 0

            # 🔹 Moyenne générale
            if not i_valid and d_valid:
                moy_general = moy_dev
            elif d_valid:
                total = sum(d_valid) + moy_interro
                count = len(d_valid) + 1
                moy_general = round(total / count, 2)
            else:
                moy_general = moy_interro

            # 🔹 Coefficient
            coefficient = notes.first().coefficient if notes.exists() else 1
            moyenne_ponderee = moy_general * coefficient if moy_general is not None else 0

            rows.append({
                "eleve": eleve,
                "int1": i_notes[0],
                "int2": i_notes[1],
                "int3": i_notes[2],
                "dev1": d_notes[0],
                "dev2": d_notes[1],
                "moy_interro": moy_interro,
                "moy_devoir": moy_dev,
                "moy_general": moy_general,
                "coefficient": coefficient,
                "moyenne_ponderee": moyenne_ponderee,
                "rang": "-"
            })

            moyennes_matiere.append((eleve, moyenne_ponderee))

        # 🔹 Classement
        moyennes_matiere.sort(key=lambda x: x[1], reverse=True)
        current_rank = 1
        for eleve, moy in moyennes_matiere:
            for r in rows:
                if r["eleve"] == eleve:
                    r["rang"] = current_rank if moy > 0 else "-"
            if moy > 0:
                current_rank += 1

    user = Login.objects.first()
    school_name = user.school_name if user else "Mon École"

    context = {
        "classe": classe,
        "annee_academique": annee_academique,
        "eleves": eleves,
        "matieres": matieres,
        "matiere_choisie": matiere_choisie,
        "trimestre": trimestre,
        "rows": rows,
        "school_name": school_name,
    }

    return render(request, "fiche_notes_detail.html", context)

import os
import requests
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from dotenv import load_dotenv
from .models import Eleve, Note

# Charger les variables d'environnement
load_dotenv()

NOM_ECOLE = "LE TRESOR DE DOWA"

def envoyer_notes(request, classe, annee_academique):
    # Récupérer le trimestre sélectionné
    trimestre = int(request.GET.get("trimestre", 1))  # Par défaut trimestre 1

    # Récupérer tous les élèves de la classe et de l'année académique
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)

    if not eleves.exists():
        return render(request, "sms.html", {"school_name": NOM_ECOLE,
                                            "classe": classe,
                                            "annee_academique": annee_academique,
                                            "recap": []})

    recap = []  # Pour stocker le statut d'envoi pour chaque élève

    for eleve in eleves:
        status = {
            "eleve": eleve,
            "email": eleve.email_parent,
            "sms": False,
            "email_sent": False,
            "note_disponible": False
        }

        # Vérifier les notes du trimestre
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre)
        if notes.exists():
            status["note_disponible"] = True
        else:
            recap.append(status)
            continue  # passer au prochain élève si pas de notes

        # Préparer les matières et calculs
        matieres_status = {}
        for n in notes:
            if n.matiere not in matieres_status:
                matieres_status[n.matiere] = {"interros": [], "devoirs": [], "moyenne_interros": 0,
                                              "moyenne_devoirs": 0, "moyenne_generale": 0}
            if n.type_note.startswith("interro"):
                matieres_status[n.matiere]["interros"].append(n.valeur)
            elif n.type_note.startswith("devoir"):
                matieres_status[n.matiere]["devoirs"].append(n.valeur)

        for matiere, status_mat in matieres_status.items():
            nb_interros = len(status_mat["interros"])
            nb_devoirs = len(status_mat["devoirs"])
            moy_interro = round(sum(status_mat["interros"]) / nb_interros, 2) if nb_interros else 0
            moy_devoirs = round(sum(status_mat["devoirs"]) / nb_devoirs, 2) if nb_devoirs else 0
            status_mat["moyenne_interros"] = moy_interro
            status_mat["moyenne_devoirs"] = moy_devoirs
            if moy_interro > 0:
                if nb_devoirs > 1:
                    status_mat["moyenne_generale"] = round((moy_interro + sum(status_mat["devoirs"])) / (1 + nb_devoirs), 2)
                elif nb_devoirs == 1:
                    status_mat["moyenne_generale"] = round((moy_interro + status_mat["devoirs"][0]) / 2, 2)
                else:
                    status_mat["moyenne_generale"] = moy_interro
            else:
                status_mat["moyenne_generale"] = moy_devoirs

        moyenne_trimestrielle = notes.first().moyenne_trimestrielle or 0
        rang = notes.first().rang or "N/A"

        if moyenne_trimestrielle >= 16:
            appreciation = "Très bien"
        elif moyenne_trimestrielle >= 14:
            appreciation = "Bien"
        elif moyenne_trimestrielle >= 12:
            appreciation = "Assez bien"
        elif moyenne_trimestrielle >= 10:
            appreciation = "Passable"
        else:
            appreciation = "Insuffisant"

        message_text = (
            f"{NOM_ECOLE}\n"
            f"Résultats du trimestre {trimestre} - {eleve.nom} {eleve.prenoms} ({eleve.classe})\n"
            f"Moyenne trimestrielle : {moyenne_trimestrielle}/20\n"
            f"Rang : {rang}\n"
            f"Appréciation : {appreciation}\n\n"
            "Merci de votre confiance et de votre soutien dans le suivi de votre enfant."
        )

        # Envoi Email HTML
        if eleve.email_parent:
            try:
                html_content = render_to_string(
                    "notes_eleve.html",
                    {"eleve": eleve,
                     "matieres_status": matieres_status,
                     "moyenne_trimestrielle": moyenne_trimestrielle,
                     "rang": rang,
                     "trimestre": trimestre,
                     "appreciation": appreciation,
                     "school_name": NOM_ECOLE})
                subject = f"{NOM_ECOLE} - Résultats du trimestre {trimestre} ({eleve.nom})"
                from_email = f"{NOM_ECOLE} <{os.getenv('EMAIL_HOST_USER')}>"
                email = EmailMultiAlternatives(subject=subject, body=message_text,
                                               from_email=from_email, to=[eleve.email_parent])
                email.attach_alternative(html_content, "text/html")
                email.send()
                status["email_sent"] = True
            except:
                status["email_sent"] = False

        recap.append(status)

    return render(request, "email_all.html", {
        "school_name": NOM_ECOLE,
        "classe": classe,
        "annee_academique": annee_academique,
        "recap": recap,
        "trimestre": trimestre
    })


def envoyer_email_notes(request, eleve_id, trimestre):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    trimestre = int(request.GET.get("trimestre", trimestre))

    if not eleve.telephone_parent and not eleve.email_parent:
        messages.error(request, f"Aucun numéro ou email enregistré pour {eleve.nom}.")
        return render(request, "email_all.html", {"eleve": eleve})

    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre)
    if not notes.exists():
        messages.error(request, f"Aucune note trouvée pour le trimestre {trimestre}.")
        return render(request, "email_all.html", {"eleve": eleve})

    # Préparer les matières et leurs notes
    matieres_status = {}
    for n in notes:
        if n.matiere not in matieres_status:
            matieres_status[n.matiere] = {
                "interros": [],
                "devoirs": [],
                "moyenne_interrogations": n.moyenne_interrogations if n.moyenne_interrogations else None,
                "moyenne_devoirs": n.moyenne_devoirs if n.moyenne_devoirs else None,
                "moyenne_generale": n.moyenne_generale if n.moyenne_generale else None,
                "notes_obj": [],
            }

        matieres_status[n.matiere]["notes_obj"].append(n)

        if n.type_note.startswith("interro"):
            matieres_status[n.matiere]["interros"].append(n.valeur)
        elif n.type_note.startswith("devoir"):
            matieres_status[n.matiere]["devoirs"].append(n.valeur)

    # Calcul des moyennes SEULEMENT si non calculé avant
    for matiere, status in matieres_status.items():

        if (
            status["moyenne_interrogations"] is not None and
            status["moyenne_devoirs"] is not None and
            status["moyenne_generale"] is not None
        ):
            continue  # Déjà calculé → on skip

        nb_interros = len(status["interros"])
        nb_devoirs = len(status["devoirs"])

        # Moyenne interros & devoirs
        moy_interro = round(sum(status["interros"]) / nb_interros, 2) if nb_interros else 0
        moy_devoirs = round(sum(status["devoirs"]) / nb_devoirs, 2) if nb_devoirs else 0

        # Moyenne générale EXACTEMENT comme ton ancien code
        if moy_interro > 0:
            if nb_devoirs > 1:
                moyenne_generale = round((moy_interro + sum(status["devoirs"])) / (1 + nb_devoirs), 2)
            elif nb_devoirs == 1:
                moyenne_generale = round((moy_interro + status["devoirs"][0]) / 2, 2)
            else:
                moyenne_generale = moy_interro
        else:
            moyenne_generale = moy_devoirs

        # Mise à jour des données calculées
        status["moyenne_interrogations"] = moy_interro
        status["moyenne_devoirs"] = moy_devoirs
        status["moyenne_generale"] = moyenne_generale

        # Mise à jour BD
        for note in status["notes_obj"]:
            note.moyenne_interrogations = moy_interro
            note.moyenne_devoirs = moy_devoirs
            note.moyenne_generale = moyenne_generale

        Note.objects.bulk_update(
            status["notes_obj"],
            ["moyenne_interrogations", "moyenne_devoirs", "moyenne_generale"]
        )

    # Moyenne trimestrielle + rang
    moyenne_trimestrielle = notes.first().moyenne_trimestrielle or 0
    rang = notes.first().rang or "N/A"

    # Appréciation trimestrielle
    if moyenne_trimestrielle >= 16:
        appreciation = "Très bien"
    elif moyenne_trimestrielle >= 14:
        appreciation = "Bien"
    elif moyenne_trimestrielle >= 12:
        appreciation = "Assez bien"
    elif moyenne_trimestrielle >= 10:
        appreciation = "Passable"
    elif moyenne_trimestrielle >= 7:
        appreciation = "Insuffisant"
    else:  # 6 et moins
        appreciation = "Faible"

   
    message_text = (
        f"{NOM_ECOLE}\n"
        f"Résultats du trimestre {trimestre} - {eleve.nom} {eleve.prenoms} ({eleve.classe})\n"
        f"Moyenne trimestrielle : {moyenne_trimestrielle}/20\n"
        f"Rang : {rang}\n"
        f"Appréciation : {appreciation}\n\n"
        "Merci de votre confiance."
    )

    # Envoi Email HTML
    if eleve.email_parent:
        try:
            html_content = render_to_string(
                "notes_eleve.html",
                {
                    "eleve": eleve,
                    "matieres_status": matieres_status,
                    "moyenne_trimestrielle": moyenne_trimestrielle,
                    "rang": rang,
                    "trimestre": trimestre,
                    "appreciation": appreciation,
                    "school_name": NOM_ECOLE,
                },
            )
            subject = f"{NOM_ECOLE} - Résultats du trimestre {trimestre} ({eleve.nom})"
            from_email = f"{NOM_ECOLE} <{os.getenv('EMAIL_HOST_USER')}>"
            email = EmailMultiAlternatives(
                subject=subject, body=message_text, from_email=from_email, to=[eleve.email_parent]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            messages.success(request, f"Email envoyé à {eleve.email_parent}.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l’envoi de l’email : {e}")

    return render(request, "email.html", {"eleve": eleve, "school_name": NOM_ECOLE})

from django.shortcuts import redirect
import os
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def envoyer_lien_ngrok(request):
    if request.method == "POST":
        try:
            fichier = r"C:\Acady\lien\lien_ngrok.txt"

            if not os.path.exists(fichier):
                # redirection avec message d'erreur
                return redirect(f"{request.META.get('HTTP_REFERER','/')}?error=Fichier+de+lien+ngrok+non+trouvé")

            with open(fichier, "r", encoding="utf-8") as f:
                lien = f.read().strip()

            destinataires = ["letresordedowa78@gmail.com"]

            subject = f"Lien ngrok généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}"
            body_text = f"Bonjour,\n\nVoici le lien ngrok :\n{lien}\n\nCordialement,\nLe serveur Django"

            body_html = render_to_string(
                "lien_ngrok_email.html",
                {"lien": lien, "date": datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}
            )

            email = EmailMultiAlternatives(
                subject=subject,
                body=body_text,
                from_email=os.getenv("EMAIL_HOST_USER"),
                to=destinataires
            )
            email.attach_alternative(body_html, "text/html")
            email.send()

            # redirection avec message succès
            return redirect(f"{request.META.get('HTTP_REFERER','/')}?success=Lien+ngrok+envoyé+avec+succès")
        except Exception as e:
            return redirect(f"{request.META.get('HTTP_REFERER','/')}?error=Erreur+lors+de+l'envoi+de+l'email:+{e}")

    return redirect('accueil')

from django.shortcuts import render
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from myapp.models import Eleve, Login

# === Vue pour la page HTML avec le bouton ===
def page_telechargement(request, classe, annee_academique):
    return render(request, 'telecharger_cartes.html', {
        'classe': classe,
        'annee_academique': annee_academique
    })

# === Vue pour générer le PDF ===
def generer_cartes_pdf(request, classe, annee_academique):
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
    user = Login.objects.first()

    logo_gauche = ImageReader(user.profile_image.path) if user.profile_image else None
    logo_droit = ImageReader(user.coin_droit.path) if user.coin_droit else None
    blason = ImageReader(user.fond_verso.path) if user.fond_verso else None

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    pw, ph = landscape(A4)

    # Dimensions cartes et positions
    carte_w, carte_h, margin = 370, 245, 25
    positions = [
        (margin, ph - carte_h - margin),
        (pw - carte_w - margin, ph - carte_h - margin),
        (margin, margin),
        (pw - carte_w - margin, margin),
    ]

    # Fond pointillé
    def fond(pdf, x, y):
        pdf.setFillColor(colors.HexColor("#D6EAF8"))
        for px in range(int(x + 15), int(x + carte_w - 15), 9):
            for py in range(int(y + 15), int(y + carte_h - 15), 9):
                pdf.circle(px, py, 0.5, fill=1, stroke=0)

    # Bordure arrondie
    def bord(pdf, x, y):
        pdf.setStrokeColor(colors.HexColor("#0033CC"))
        pdf.setLineWidth(2)
        pdf.roundRect(x, y, carte_w, carte_h, 14, stroke=1, fill=0)

    # RECTO
    for i, eleve in enumerate(eleves):
        if i % 4 == 0 and i != 0:
            pdf.showPage()
        x, y = positions[i % 4]
        fond(pdf, x, y)
        bord(pdf, x, y)
        center = x + carte_w / 2

        if logo_gauche:
            pdf.drawImage(logo_gauche, x + 18, y + carte_h - 65, width=50, height=50, preserveAspectRatio=True)
        if logo_droit:
            pdf.drawImage(logo_droit, x + carte_w - 70, y + carte_h - 65, width=50, height=50, preserveAspectRatio=True)

        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(colors.black)
        pdf.drawCentredString(center, y + carte_h - 15, "REPUBLIQUE DU BENIN")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(colors.HexColor("#0033CC"))
        pdf.drawCentredString(center, y + carte_h - 35, "MINISTÈRE DES ENSEIGNEMENTS SECONDAIRE,")
        pdf.drawCentredString(center, y + carte_h - 48, "TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE")
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(center, y + carte_h - 65, "DDEMP : OUEME")
        pdf.setFillColor(colors.red)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(center, y + carte_h - 85, f"Année scolaire : {annee_academique}")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.setFillColor(colors.black)
        pdf.drawCentredString(center, y + carte_h - 110, "C.S.P LE TRÉSOR DE DOWA")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(center, y + carte_h - 130, "Tel : 0197884441 Porto-Novo")
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(center, y + carte_h - 152, "CARTE D’IDENTITÉ SCOLAIRE")

        # Informations élève
        info_x, info_y, spacing = x + 25, y + carte_h - 180, 20
        def info(label, value):
            nonlocal info_y
            pdf.setFont("Helvetica-Bold", 12)
            pdf.setFillColor(colors.black)
            pdf.drawString(info_x, info_y, f"{label} :")
            pdf.line(info_x, info_y - 2, info_x + 75, info_y - 2)
            pdf.setFont("Helvetica", 12)
            pdf.drawString(info_x + 85, info_y, str(value))
            info_y -= spacing

        info("NOM", eleve.nom)
        info("Prénoms", eleve.prenoms)
        info("Né(e) le", f"{eleve.date_naissance} à {eleve.lieu_naissance}")
        info("Sexe", eleve.sexe)
        info("Classe", eleve.classe)
        info("Éducmaster", eleve.matricule)

        # Photo
        if eleve.profile_eleve:
            pdf.drawImage(ImageReader(eleve.profile_eleve.path),
                          x + carte_w - 115, y + carte_h - 200,
                          width=95, height=125, preserveAspectRatio=True, mask="auto")

    # VERSO
    pdf.showPage()
    for x, y in positions:
        fond(pdf, x, y)
        bord(pdf, x, y)
        pdf.setFillColor(colors.red)
        pdf.rect(x + 25, y + carte_h - 60, 25, 12, fill=1)
        pdf.setFillColor(colors.yellow)
        pdf.rect(x + 50, y + carte_h - 60, 25, 12, fill=1)
        pdf.setFillColor(colors.green)
        pdf.rect(x + 75, y + carte_h - 60, 25, 12, fill=1)
        if blason:
            pdf.drawImage(blason, x + carte_w - 130, y + carte_h - 160, width=110, height=110)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(x + carte_w / 2, y + 30, "LE DIRECTEUR")

    pdf.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="cartes.pdf"'})
                        
from django.shortcuts import render, redirect
from django.contrib import messages
from myapp.models import Eleve, Enseignant, Note

def inserer_notes_classe_enseignant(request, classe, annee_academique):
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        return redirect('enseignant_login')

    try:
        enseignant = Enseignant.objects.get(id=enseignant_id)
    except Enseignant.DoesNotExist:
        return redirect('enseignant_login')

    # Matière choisie depuis le dashboard
    matiere_choisie = request.GET.get("matiere")
    if not matiere_choisie:
        messages.error(request, "Veuillez choisir une matière depuis le dashboard.")
        return redirect('dashboard_enseignant')

    # Récupérer les élèves
    eleves = Eleve.objects.filter(classe=classe, annee_academique=annee_academique).order_by("nom", "prenoms")

    type_notes = ["interro1", "interro2", "interro3", "devoir1", "devoir2"]

    # Notes existantes
    all_notes = Note.objects.filter(eleve__in=eleves, matiere=matiere_choisie, annee_academique=annee_academique)
    notes_existantes = {}
    for eleve in eleves:
        notes_eleve = {}
        for n in all_notes.filter(eleve_id=eleve.id):
            key = f"{n.type_note}_{n.trimestre}"
            notes_eleve[key] = n.valeur
        notes_existantes[str(eleve.id)] = notes_eleve

    if request.method == "POST":
        type_note = request.POST.get("type_note")
        trimestre = int(request.POST.get("trimestre", 1))

        updates, creations = [], []

        for eleve in eleves:
            valeur = request.POST.get(f"note_{eleve.id}")
            if valeur:
                try:
                    valeur = float(valeur)
                    if not (0 <= valeur <= 20):
                        raise ValueError("La note doit être entre 0 et 20.")

                    note_obj = next((n for n in all_notes if n.eleve_id == eleve.id and n.type_note == type_note and n.trimestre == trimestre), None)
                    if note_obj:
                        note_obj.valeur = valeur
                        updates.append(note_obj)
                    else:
                        creations.append(Note(
                            eleve=eleve,
                            matiere=matiere_choisie,
                            type_note=type_note,
                            valeur=valeur,
                            trimestre=trimestre,
                            annee_academique=annee_academique
                        ))
                except ValueError:
                    messages.error(request, f"Note invalide pour {eleve.nom} {eleve.prenoms}")

        if updates:
            Note.objects.bulk_update(updates, ["valeur"])
        if creations:
            Note.objects.bulk_create(creations)

        messages.success(request, "Les notes ont été enregistrées avec succès.")
        return redirect(f"/enseignant/notes/{classe}/{annee_academique}/?matiere={matiere_choisie}")

    school_name = "CPEG LE TRÉSOR DE DOWA"

    return render(request, "enseignant/inserer_notes.html", {
        "eleves": eleves,
        "classe": classe,
        "annee_academique": annee_academique,
        "school_name": school_name,
        "type_notes": type_notes,
        "notes_existantes": notes_existantes,
        "enseignant": enseignant,
        "matiere_choisie": matiere_choisie,
        "type_note": type_notes[0],
        "trimestre": 1,
    })


from django.shortcuts import render, redirect
from .models import Eleve, Note, Enseignant
from django.contrib import messages

def fiche_notes_detail_enseignant(request, classe, annee_academique):
    # Vérifier que l'enseignant est connecté
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('enseignant_login')

    try:
        enseignant = Enseignant.objects.get(id=enseignant_id)
    except Enseignant.DoesNotExist:
        messages.error(request, "Profil enseignant introuvable.")
        return redirect('enseignant_login')

    matiere_choisie = request.GET.get("matiere", enseignant.matiere)

    trimestre = int(request.GET.get("trimestre", 1))

    eleves = Eleve.objects.filter(
        classe=classe,
        annee_academique=annee_academique
    ).order_by("nom", "prenoms")

    rows = []
    moyennes_matiere = []

    for eleve in eleves:
        notes = Note.objects.filter(
            eleve=eleve,
            matiere=matiere_choisie,
            trimestre=trimestre,
            annee_academique=annee_academique
        )

        # 🔹 Récupération triée des interros
        i_notes = [
            notes.filter(type_note="interro1").first().valeur if notes.filter(type_note="interro1").exists() else None,
            notes.filter(type_note="interro2").first().valeur if notes.filter(type_note="interro2").exists() else None,
            notes.filter(type_note="interro3").first().valeur if notes.filter(type_note="interro3").exists() else None,
        ]

        # 🔹 Récupération triée des devoirs
        d_notes = [
            notes.filter(type_note="devoir1").first().valeur if notes.filter(type_note="devoir1").exists() else None,
            notes.filter(type_note="devoir2").first().valeur if notes.filter(type_note="devoir2").exists() else None,
        ]

        # 🔹 Calculs
        i_valid = [n for n in i_notes if n is not None]
        d_valid = [n for n in d_notes if n is not None]

        moy_interro = round(sum(i_valid) / len(i_valid), 2) if i_valid else 0
        moy_dev = round(sum(d_valid) / len(d_valid), 2) if d_valid else 0

        # Moyenne générale
        if not i_valid and d_valid:
            moy_general = moy_dev
        elif d_valid:
            total = sum(d_valid) + moy_interro
            count = len(d_valid) + 1
            moy_general = round(total / count, 2)
        else:
            moy_general = moy_interro

        coefficient = notes.first().coefficient if notes.exists() else 1
        moyenne_ponderee = moy_general * coefficient if moy_general is not None else 0

        rows.append({
            "eleve": eleve,
            "int1": i_notes[0],
            "int2": i_notes[1],
            "int3": i_notes[2],
            "dev1": d_notes[0],
            "dev2": d_notes[1],
            "moy_interro": moy_interro,
            "moy_devoir": moy_dev,
            "moy_general": moy_general,
            "coefficient": coefficient,
            "moyenne_ponderee": moyenne_ponderee,
            "rang": "-"
        })

        moyennes_matiere.append((eleve, moyenne_ponderee))

    # 🔹 Classement
    moyennes_matiere.sort(key=lambda x: x[1], reverse=True)
    current_rank = 1
    for eleve, moy in moyennes_matiere:
        for r in rows:
            if r["eleve"] == eleve:
                r["rang"] = current_rank if moy > 0 else "-"
        if moy > 0:
            current_rank += 1

    school_name = "LE TRESOR DE DOWA"

    context = {
        "classe": classe,
        "annee_academique": annee_academique,
        "eleves": eleves,
        "matiere_choisie": matiere_choisie,
        "trimestre": trimestre,
        "rows": rows,
        "school_name": school_name,
    }

    return render(request, "enseignant/fiche_notes_detail.html", context)

from django.shortcuts import render, redirect
from .models import Enseignant, Horaire

from django.shortcuts import render
from .models import Enseignant, Horaire

def liste_enseignants(request):
    enseignants = Enseignant.objects.all().order_by('nom', 'prenoms')
    horaires = Horaire.objects.all().order_by('classe', 'jour', 'heure_debut')

    context = {
        "enseignants": enseignants,
        "horaires": horaires,
    }

    # Lire le message depuis GET
    if 'success' in request.GET:
        context['success'] = request.GET.get('success')
    if 'error' in request.GET:
        context['error'] = request.GET.get('error')

    return render(request, "enseignant/liste_enseignants.html", context)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Enseignant, Horaire

def modifier_horaire(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    horaires = Horaire.objects.filter(enseignant=enseignant).order_by('classe', 'jour', 'heure_debut')
    
    # Récupérer les classes distinctes de l'enseignant
    classes = enseignant.classes.split(',')  # si tu stockes plusieurs classes séparées par virgule

    # Liste des jours
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]

    if request.method == "POST":
        horaire_id = request.POST.get("horaire_id")
        classe = request.POST.get("classe")
        jour = request.POST.get("jour")
        heure_debut = request.POST.get("heure_debut")
        heure_fin = request.POST.get("heure_fin")

        horaire = get_object_or_404(Horaire, id=horaire_id)
        horaire.classe = classe
        horaire.jour = jour
        horaire.heure_debut = heure_debut
        horaire.heure_fin = heure_fin
        horaire.save()

        messages.success(request, "Horaire modifié avec succès !")
        return redirect(request.path)  # reste sur la même page

    return render(request, "enseignant/modifier_horaire.html", {
        "enseignant": enseignant,
        "horaires": horaires,
        "classes": classes,
        "jours": jours
    })

from django.shortcuts import render, get_object_or_404
from .models import Enseignant, Horaire

def ajouter_horaire(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
    classes = [c.strip() for c in enseignant.classes.split(',')]

    message = ""  # variable pour afficher le message

    if request.method == "POST":
        classe = request.POST.get("classe")
        jour = request.POST.get("jour")
        heure_debut = request.POST.get("heure_debut")
        heure_fin = request.POST.get("heure_fin")

        if classe and jour and heure_debut and heure_fin:
            Horaire.objects.create(
                classe=classe,
                jour=jour,
                heure_debut=heure_debut,
                heure_fin=heure_fin,
                matiere=enseignant.matiere,
                enseignant=enseignant,
                annee_academique=enseignant.annee_academique
            )
            message = "Horaire enregistré avec succès !"

    context = {
        "enseignant": enseignant,
        "jours": jours,
        "classes": classes,
        "message": message,
    }
    return render(request, "enseignant/ajouter_horaire.html", context)

def supprimer_enseignant(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    enseignant.delete()
    # redirection vers la page liste_enseignants avec message spécifique
    return redirect(f"{request.META.get('HTTP_REFERER','/')}?success=Enseignant+supprimé+avec+succès")

from django.shortcuts import render
from django.utils.dateparse import parse_date
from .models import Note, Enseignant

def consulter_notes(request):
    date_str = request.GET.get('date')
    classe_nom = request.GET.get('classe')
    
    notes = []

    if date_str and classe_nom:
        date_obj = parse_date(date_str)  # convertir la date string en date
        # Récupérer les notes pour la classe et la date
        notes = Note.objects.filter(
            eleve__classe=classe_nom,
            date_ajout__date=date_obj
        ).select_related('eleve')
        
        # Ajouter le nom de l'enseignant à chaque note
        for note in notes:
            enseignant = Enseignant.objects.filter(
                classes=note.eleve.classe,
                matiere=note.matiere,
                annee_academique=note.annee_academique
            ).first()
            note.nom_enseignant = f"{enseignant.nom} {enseignant.prenoms}" if enseignant else "N/A"

    return render(request, 'notes_jour.html',{
        'notes': notes,
        'classe': classe_nom,
        'date': date_str
    })

def suivre_eleve_form(request):
    return render(request, 'enseignant/suivre_eleve_form.html')

from django.shortcuts import render, get_object_or_404
from .models import Eleve, Note, Login


from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render
from .models import Eleve, Note, Login

def suivre_eleve_resultat(request):
    numero = request.GET.get("educmaster")
    trimestre = int(request.GET.get("trimestre", 1))

    if not numero:
        return render(request, "error.html", {"message": "Veuillez entrer un numéro EducMaster."})

    # 🔍 Rechercher l'élève
    try:
        eleve = Eleve.objects.get(matricule=numero)
    except Eleve.DoesNotExist:
        return render(request, "error.html", {"message": "Aucun élève trouvé avec ce numéro EducMaster."})

    annee = eleve.annee_academique.strip()

    # 🔢 Toutes les notes du trimestre
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee)

    if not notes.exists():
        return render(request, "error.html", {"message": "Aucune note trouvée pour cet élève."})

    # ------------------------------------------------------------
    #   PARTIE 1 : Regroupement par matières
    # ------------------------------------------------------------
    matieres_status = {}
    for n in notes:
        if n.matiere not in matieres_status:
            matieres_status[n.matiere] = {
                "interros": [],
                "devoirs": [],
                "moyenne_interros": n.moyenne_interrogations,
                "moyenne_devoirs": n.moyenne_devoirs,
                "moyenne_generale": n.moyenne_generale,
                "coefficient": n.coefficient if n.coefficient else 1
            }

        if n.type_note.startswith("interro"):
            matieres_status[n.matiere]["interros"].append(Decimal(n.valeur))
        if n.type_note.startswith("devoir"):
            matieres_status[n.matiere]["devoirs"].append(Decimal(n.valeur))

    # ------------------------------------------------------------
    #   PARTIE 2 : Calcul des moyennes par matière si manquantes
    # ------------------------------------------------------------
    recalcul_trimestrielle = False
    for matiere, status in matieres_status.items():
        # Moyenne interros
        if (status["moyenne_interros"] in [None, 0]) and status["interros"]:
            status["moyenne_interros"] = sum(status["interros"]) / Decimal(len(status["interros"]))
            status["moyenne_interros"] = status["moyenne_interros"].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            recalcul_trimestrielle = True

        # Moyenne devoirs
        if (status["moyenne_devoirs"] in [None, 0]) and status["devoirs"]:
            status["moyenne_devoirs"] = sum(status["devoirs"]) / Decimal(len(status["devoirs"]))
            status["moyenne_devoirs"] = status["moyenne_devoirs"].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            recalcul_trimestrielle = True

        # Moyenne générale
        if (status["moyenne_generale"] in [None, 0]) and status["devoirs"]:
            total = (status["moyenne_interros"] if status["interros"] else Decimal('0.00')) + sum(status["devoirs"])
            nb = (1 if status["interros"] else 0) + len(status["devoirs"])
            status["moyenne_generale"] = (total / Decimal(nb)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            recalcul_trimestrielle = True

        # Sauvegarder si nouveau calcul
        if recalcul_trimestrielle:
            for note_obj in notes.filter(matiere=matiere):
                note_obj.moyenne_interrogations = float(status["moyenne_interros"])
                note_obj.moyenne_devoirs = float(status["moyenne_devoirs"])
                note_obj.moyenne_generale = float(status["moyenne_generale"])
                note_obj.save()

    # ------------------------------------------------------------
    #   PARTIE 3 : Moyenne trimestrielle
    # ------------------------------------------------------------
    note_first = notes.first()
    if (note_first.moyenne_trimestrielle not in [None, 0]) and not recalcul_trimestrielle:
        moyenne_trimestrielle = Decimal(note_first.moyenne_trimestrielle)
    else:
        total_notes = Decimal('0.00')
        total_coef = Decimal('0.00')

        for matiere, status in matieres_status.items():
            if status["moyenne_generale"]:
                total_notes += status["moyenne_generale"] * Decimal(status["coefficient"])
                total_coef += Decimal(status["coefficient"])

        moyenne_trimestrielle = (total_notes / total_coef).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total_coef > 0 else Decimal('0.00')

        # Sauvegarder la moyenne
        for n in notes:
            n.moyenne_trimestrielle = float(moyenne_trimestrielle)
            n.save()

    # ------------------------------------------------------------
    #   PARTIE 4 : Rang
    # ------------------------------------------------------------
    if (note_first.rang not in [None, 0]) and not recalcul_trimestrielle:
        rang = note_first.rang
    else:
        eleves_classe = Eleve.objects.filter(classe=eleve.classe, annee_academique=annee)
        moyennes = []
        for e in eleves_classe:
            n = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee).first()
            moy = Decimal(n.moyenne_trimestrielle) if n and n.moyenne_trimestrielle else Decimal('0.00')
            moyennes.append((e, moy))

        moyennes_sorted = sorted(moyennes, key=lambda x: x[1], reverse=True)
        for index, (e, _) in enumerate(moyennes_sorted):
            notes_e = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee)
            for n in notes_e:
                n.rang = index + 1
                n.save()
        rang = next((i + 1 for i, (e, m) in enumerate(moyennes_sorted) if e == eleve), 0)

    # ------------------------------------------------------------
    #   PARTIE 5 : Appréciation / mention
    # ------------------------------------------------------------
    m = moyenne_trimestrielle
    if m >= Decimal('16.00'):
        appreciation = "Très bien"
    elif m >= Decimal('14.00'):
        appreciation = "Bien"
    elif m >= Decimal('12.00'):
        appreciation = "Assez bien"
    elif m >= Decimal('10.00'):
        appreciation = "Passable"
    else:
        appreciation = "Insuffisant"

    # ------------------------------------------------------------
    #   PARTIE 6 : Informations école
    # ------------------------------------------------------------
    login = Login.objects.first()
    school_name = login.school_name if login else ""
    logo = login.profile_image if login else None

    # ------------------------------------------------------------
    #   PARTIE 7 : Contexte pour template
    # ------------------------------------------------------------
    context = {
        "eleve": eleve,
        "classe": eleve.classe,
        "matieres_status": matieres_status,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "rang": rang,
        "trimestre": trimestre,
        "school_name": school_name,
        "logo": logo,
        "appreciation": appreciation,
    }

    return render(request, "enseignant/suivre_eleve_resultat.html", context)


from django.shortcuts import render, get_object_or_404
from myapp.models import Enseignant, Horaire

def mon_emploi_du_temps(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)

    # Récupérer les horaires
    horaires = Horaire.objects.filter(enseignant=enseignant).order_by('classe', 'jour', 'heure_debut')
    classes_distinctes = horaires.values_list('classe', flat=True).distinct()
    jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']

    return render(request, 'enseignant/mon_emploi_du_temps.html', {
        'enseignant': enseignant,
        'horaires': horaires,
        'classes_distinctes': classes_distinctes,
        'jours': jours
    })
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Eleve, Horaire, Presence
from django.utils import timezone

def marquer_presence(request, classe_nom, horaire_id):
    horaire = get_object_or_404(Horaire, id=horaire_id)
    eleves = Eleve.objects.filter(
        classe=classe_nom, 
        annee_academique=horaire.annee_academique
    ).order_by('nom', 'prenoms')

    if request.method == 'POST':
        for eleve in eleves:
            etat = request.POST.get(f'presence_{eleve.id}')
            motif = request.POST.get(f'motif_{eleve.id}', '')

            if etat:
                presence_obj = Presence.objects.create(
                    eleve=eleve,
                    enseignant=horaire.enseignant,
                    classe=classe_nom,
                    date=timezone.now(),
                    etat='present' if etat == 'oui' else 'absent',
                    horaire=horaire,
                )
                if etat == 'non':
                    presence_obj.motif = motif
                    presence_obj.save()

        messages.success(request, "Présences enregistrées avec succès !")
        return redirect('marquer_presence', classe_nom=classe_nom, horaire_id=horaire.id)

    return render(request, 'enseignant/marquer_presence.html', {
        'eleves': eleves,
        'classe_nom': classe_nom,
        'horaire': horaire
    })

from django.shortcuts import render, redirect
from .models import Enseignant, Presence
from datetime import datetime
import calendar

def heures_mensuelles(request):
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        return redirect('enseignant_login')

    enseignant = Enseignant.objects.get(id=enseignant_id)

    # Récupérer toutes les présences avec horaire non nul
    presences = Presence.objects.filter(
        enseignant=enseignant,
        etat='present',
        horaire__isnull=False
    ).select_related('horaire').order_by('date', 'horaire')

    heures_par_mois = {}
    vus = set()  # pour éviter de compter plusieurs fois le même horaire le même jour

    for p in presences:
        key = (p.date, p.horaire.id)
        if key in vus:
            continue  # déjà compté
        vus.add(key)

        duree = (datetime.combine(datetime.today(), p.horaire.heure_fin) -
                 datetime.combine(datetime.today(), p.horaire.heure_debut))
        heures = duree.total_seconds() / 3600
        mois = p.date.month
        heures_par_mois[mois] = heures_par_mois.get(mois, 0) + heures

    heures_par_mois_noms = {calendar.month_name[m]: round(h, 2) for m, h in heures_par_mois.items()}

    return render(request, 'enseignant/heures_mensuelles.html', {
        'enseignant': enseignant,
        'heures_par_mois': heures_par_mois_noms
    })

from django.shortcuts import render
from .models import Presence

def liste_absents(request):
    date_filter = request.GET.get('date')  # filtre par date

    # Récupérer les présences absentes
    presences = Presence.objects.filter(etat='absent').select_related('horaire', 'enseignant', 'eleve')

    if date_filter:
        presences = presences.filter(date=date_filter)

    # Grouper par classe de l'élève
    classes = {}
    for p in presences:
        classe = p.classe
        if classe not in classes:
            classes[classe] = []
        classes[classe].append(p)

    return render(request, 'liste_absents.html', {
        'classes': classes,
        'date_filter': date_filter
    })

from datetime import datetime, timedelta
from django.shortcuts import render
import calendar
from .models import Presence, Enseignant

def heures_mensuelles_recap(request):
    mois_filter = request.GET.get("mois")  # ex : "06" pour Juin

    presences = Presence.objects.select_related("horaire__enseignant").filter(
        horaire__isnull=False
    ).order_by('date', 'horaire')

    heures_par_enseignant = {}  # { enseignant_id: { 'enseignant': objet, 'matieres': {matiere: heures} } }
    vus = set()  # pour ne pas compter 2 fois le même cours le même jour

    for p in presences:
        key = (p.date, p.horaire.id)
        if key in vus:
            continue
        vus.add(key)

        enseignant = p.horaire.enseignant
        matiere = enseignant.matiere

        dt_debut = datetime.combine(datetime.today(), p.horaire.heure_debut)
        dt_fin = datetime.combine(datetime.today(), p.horaire.heure_fin)
        if dt_fin < dt_debut:
            dt_fin += timedelta(days=1)
        duree = (dt_fin - dt_debut).total_seconds() / 3600

        # Filtrer par mois
        if mois_filter and int(mois_filter) != p.date.month:
            continue

        if enseignant.id not in heures_par_enseignant:
            heures_par_enseignant[enseignant.id] = {
                'enseignant': enseignant,
                'matieres': {}
            }

        if matiere not in heures_par_enseignant[enseignant.id]['matieres']:
            heures_par_enseignant[enseignant.id]['matieres'][matiere] = 0

        heures_par_enseignant[enseignant.id]['matieres'][matiere] += duree

    mois_options = [{"num": f"{m:02d}", "nom": calendar.month_name[m]} for m in range(1, 13)]

    return render(request, "heures_mensuelles.html", {
        "heures_par_enseignant": heures_par_enseignant,
        "mois_filter": mois_filter,
        "mois_options": mois_options,
    })
