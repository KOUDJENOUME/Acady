from django.contrib import admin
from .models import Eleve, Note, Login,Presence

@admin.register(Login)
class LoginAdmin(admin.ModelAdmin):
    list_display = ('username','name','school_name','profile_image','email','numero','password')
@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom', 'prenoms', 'email_parent','telephone_parent' , 'matricule', 'sexe', 'classe', 'annee_academique','profile_eleve','date_enregistrement')
    list_filter = ('annee_academique', 'sexe', 'classe', 'date_enregistrement')
    search_fields = ('nom', 'prenoms', 'classe', 'sexe', 'annee_academique')
    ordering = ('date_enregistrement',)

from django.contrib import admin
from .models import Horaire

@admin.register(Horaire)
class HoraireAdmin(admin.ModelAdmin):
    list_display = ('classe', 'jour', 'heure_debut', 'heure_fin', 'matiere', 'enseignant', 'annee_academique')
    list_filter = ('classe', 'jour', 'enseignant', 'annee_academique')
    search_fields = ('classe', 'matiere', 'enseignant__nom', 'enseignant__prenoms')


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ('enseignant', 'classe', 'date', 'etat', 'horaire', 'motif')
    list_filter = ('date', 'classe', 'etat')
    search_fields = ('enseignant__nom', 'enseignant__prenoms', 'classe', 'motif')



@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'matiere', 'trimestre', 'valeur', 'type_note', 'coefficient', 'moyenne_interrogations', 'moyenne_devoirs', 'moyenne_generale', 'moyenne_trimestrielle', 'rang','annee_academique','date_ajout')
    list_filter = ('matiere', 'type_note', 'date_ajout')
    search_fields = ('eleve__nom',)

from .models import Enseignant

class EnseignantAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'email', 'matiere', 'password', 'annee_academique', 'is_verified','classes')
    list_filter = ('matiere', 'annee_academique', 'is_verified')
    search_fields = ('nom', 'prenoms', 'email')
    ordering = ('nom',)

admin.site.register(Enseignant, EnseignantAdmin)
