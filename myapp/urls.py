from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.choix_role, name='choix_role'),
    path('login/', views.connexion, name='login'),
    path('enseignant/login/', views.enseignant_login, name='enseignant_login'), 
    path('enseignant/dashboard/', views.dashboard_enseignant, name='dashboard_enseignant'),
    path("register/", views.register_enseignant, name="register_enseignant"),
    path('enseignant/<int:enseignant_id>/ajouter_horaire/', views.ajouter_horaire, name='ajouter_horaire'),
    path('enseignants/<int:enseignant_id>/modifier_horaire/', views.modifier_horaire, name='modifier_horaire'),
    path('enseignant/<int:enseignant_id>/emploi_du_temps/', views.mon_emploi_du_temps, name='mon_emploi_du_temps'),
    path('reset/', views.reset_utilisateurs, name='reset_utilisateurs'),
    path('inscription/', views.inscription, name='inscription'),
    # urls.py
    path('presence/<str:classe_nom>/<int:horaire_id>/', views.marquer_presence, name='marquer_presence'),
   # URL pour le récapitulatif des heures (ex: par enseignant ou autre vue)
    path('gestion/heures_mensuelles_recap/', views.heures_mensuelles_recap, name='heures_mensuelles_recap'),

# URL pour le calcul détaillé des heures mensuelles
    path('gestion/heures_mensuelles/', views.heures_mensuelles, name='heures_mensuelles'),

# URL pour la liste des absents
    path('gestion/absents/', views.liste_absents, name='liste_absents'),

    path('accueil/', views.accueil_view, name='accueil'),
    path('classe/<str:classe>/<str:annee_academique>/inserer-notes/', views.inserer_notes_classe_view, name='inserer_notes_classe'),
    path('modifier_note/classe/<str:classe>/<str:annee_academique>/', views.modifier_note, name='modifier_note'),
    path('supprimer/<int:id_eleve>/', views.supprimer_eleve, name='supprimer_eleve'),
    path('bulletin_trimestre1/<str:classe>/<int:eleve_id>/', views.bulletin_trimestre1, name='trimestre1'),
    path('bulletin_trimestre2/<str:classe>/<int:eleve_id>/', views.bulletin_trimestre2, name='trimestre2'),
    path('bulletin_trimestre3/<str:classe>/<int:eleve_id>/', views.bulletin_trimestre3, name='trimestre3'),
    path('trimestre1/<str:classe>/<str:annee_academique>/',views.affichemoy_trimestre1 , name='trimestre_1'),
    path('trimestre2/<str:classe>/<str:annee_academique>/', views.affichemoy_trimestre2, name='trimestre_2'),
    path('trimestre3/<str:classe>/<str:annee_academique>/', views.affichemoy_trimestre3, name='trimestre_3'),
    path(
        'fiche_notes/<str:classe>/<str:annee_academique>/',
        views.fiche_notes_detail,
        name='fiche_notes_detail'
    ),
    # URL pour Excel Trimestre 1
    path('trimestreexcel1/<str:classe>/<str:annee_academique>/', 
         views.affichemoyexcel_trimestre1, name='trimestre1_excel'),

    # Si besoin, tu peux faire pareil pour Trimestre 2 et 3
    path('trimestreexcel2/<str:classe>/<str:annee_academique>/', 
         views.affichemoyexcel_trimestre2, name='trimestre2_excel'),

    path('trimestreexcel3/<str:classe>/<str:annee_academique>/', 
         views.affichemoyexcel_trimestre3, name='trimestre3_excel'),path('enregistrer_eleve/', views.enregistrer_eleve, name='enregistrer_eleve'),
    path('modifier_eleve/<str:classe>/<int:eleve_id>/<str:annee>/', views.modifier_eleve, name='modifier_eleve'),
    path('6eme/<str:annee>/', views.afficher_sixieme, name='afficher_sixieme'),
    path('5eme/<str:annee>/', views.afficher_cinquieme, name='afficher_cinquieme'),
    path('4eme/<str:annee>/', views.afficher_quatrieme, name='afficher_quatrieme'),
    path('3eme/<str:annee>/', views.afficher_troisieme, name='afficher_troisieme'),
    path('eleve/<int:eleve_id>/', views.notes_eleve, name='notes_eleve'),
    path('liste_eleves/<str:classe>/<str:annee_academique>/',views.liste_eleves , name='liste_eleves'),
    path('fiche_note/<str:classe>/<str:annee_academique>/',views.fiche_note , name='fiche_note'),
    path('shutdown/', views.shutdown_server, name='shutdown'),
    # Liste des élèves / actions
    path('choisir_trimestre/<int:eleve_id>/', views.choisir_trimestre, name='choisir_trimestre'),
    path('envoyer/<str:classe>/<str:annee_academique>/', views.envoyer_notes, name='envoyer_notes'),
    path('envoyer_email/<int:eleve_id>/<int:trimestre>/', views.envoyer_email_notes, name='envoyer_email_notes'),
    path('envoi_lien_ngrok/', views.envoyer_lien_ngrok, name='envoi_lien_ngrok'),
    path('cartes/<str:classe>/<str:annee_academique>/', views.generer_cartes_pdf, name='generer_cartes_pdf'),
    path('enseignant/notes/<str:classe>/<str:annee_academique>/', 
     views.inserer_notes_classe_enseignant, name='inserer_notes_classe_enseignant'),
    path('enseignant/logout/', views.enseignant_logout, name='enseignant_logout'),
    path('notes/<str:classe>/<str:annee_academique>/voir/', views.fiche_notes_detail_enseignant, name='fiche_notes_detail_enseignant'),
    path('enseignant/verification-otp/', views.enseignant_verification_otp, name='enseignant_verification_otp'),
    path("enseignants/", views.liste_enseignants, name="liste_enseignants"),
    path("enseignants/supprimer/<int:enseignant_id>/", views.supprimer_enseignant, name="supprimer_enseignant"),
    path('consulter-notes/', views.consulter_notes, name='consulter_notes'),
    path("enseignant/mdp_oublie/", views.enseignant_mdp_oublie, name="enseignant_mdp_oublie"),
    path("enseignant/mdp_oublie/otp/", views.enseignant_mdp_oublie_otp, name="enseignant_mdp_oublie_otp"),
    path("enseignant/mdp_oublie/reset/", views.enseignant_mdp_oublie_reset, name="enseignant_mdp_oublie_reset"),
    path('enseignant/suivre-eleve/', views.suivre_eleve_form, name='suivre_eleve'),
    path('enseignant/suivre-eleve/resultat/', views.suivre_eleve_resultat, name='suivre_eleve_resultat'),
    path("enseignant/reset/", views.enseignant_mdp_oublie_reset, name="enseignant_mdp_oublie_reset"),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)