from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Login(models.Model):
    username = models.CharField(max_length=100)
    school_name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    email= models.CharField(max_length=100)
    numero = models.CharField(max_length=100)
    name = models.CharField(max_length=100,null=True)
    profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)
    coin_droit = models.ImageField(upload_to="cartes/recto/", blank=True, null=True)
    fond_verso = models.ImageField(upload_to="cartes/verso/", blank=True, null=True)

class Enseignant(models.Model):
    nom = models.CharField(max_length=150)
    prenoms = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    matiere = models.CharField(max_length=255, blank=True)
    classes = models.CharField(max_length=100)  # <-- juste un attribut simple
    annee_academique = models.CharField(max_length=20)
    is_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nom} {self.prenoms}"
       
class Eleve(models.Model):
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=100)
    classe = models.CharField(max_length=50)
    annee_academique = models.CharField(max_length=50)
    sexe = models.CharField(max_length=10, choices=[('M', 'Masculin'), ('F', 'Feminin')])  # Exemple
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    matricule = models.CharField(max_length=50,null=True)
    telephone_parent = models.CharField(max_length=15, blank=True, null=True)  # exemple
    email_parent = models.CharField(max_length=15, blank=True, null=True)  # exemple
    # 🔹 Champs ajoutés (facultatifs)
    date_naissance = models.DateField(blank=True, null=True)
    lieu_naissance = models.CharField(max_length=100, blank=True, null=True)
    nationalite = models.CharField(max_length=50, blank=True, null=True)
    profile_eleve = models.ImageField(upload_to="profile_images/", blank=True, null=True)
    
    def __str__(self):
        return f"{self.nom} {self.prenoms}"
    def calculer_moyenne(self, trimestre,annee_academique):
        """
        Calcule la moyenne de l'élève pour un trimestre donné.
        """
        # Récupérer toutes les notes de l'élève pour le trimestre
        notes = Note.objects.filter(eleve=self, trimestre=trimestre,annee_academique=annee_academique)
        
        # Calculer la moyenne pondérée
        total_notes_ponderees = 0
        total_coefficients = 0
        
        for note in notes:
            coefficient = note.coefficient# Récupère le coefficient de la note
            total_notes_ponderees += note.valeur * coefficient
            total_coefficients += coefficient
        
        # Calcul de la moyenne trimestrielle
        if total_coefficients > 0:
            return total_notes_ponderees / total_coefficients
        return 0

class Note(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    matiere = models.CharField(max_length=100)
    trimestre = models.IntegerField()
    valeur = models.FloatField()
    type_note = models.CharField(max_length=20)
    coefficient = models.IntegerField(default=2)
    moyenne_interrogations = models.FloatField(null=True, blank=True)
    moyenne_devoirs = models.FloatField(null=True, blank=True)
    moyenne_generale = models.FloatField(null=True, blank=True)
    annee_academique = models.CharField(max_length=10)
    moyenne_trimestrielle = models.FloatField(null=True,blank=True, default = 0.0)
    rang = models.IntegerField(null=True, blank=True)  # Champ rang pour enregistrer le rang
    date_ajout = models.DateTimeField(default=timezone.now)  # Exemple
    annee_academique= models.CharField(max_length=10, blank=True,null=True)
    def __str__(self):
        return f"{self.eleve} - {self.matiere} - {self.trimestre}"
    def save(self, *args, **kwargs):
        # Si l'année académique n'est pas définie, on la prend de l'élève
        if not self.eleve and not self.annee_academique:
            self.annee_academique = self.eleve.annee_academique
        super().save(*args, **kwargs)
    @property
    def coefficient(self):
        # Si l'élève est en 4ème ou 3ème, appliquer les coefficients spécifiques
        if self.eleve.classe in ['4ème', '3ème']:
            if self.matiere == 'Mathématiques':
                return 3
            elif self.matiere == 'EPS' or self.matiere == 'Informatique' or self.matiere == 'Conduite' :
                return 1
            else:
                return 2
        # Si l'élève est en 6ème ou 5ème, mettre le coefficient à 1 pour toutes les matières
        elif self.eleve.classe in ['6ème', '5ème']:
            return 1
        else:
            return 0  # Cas où la classe de l'élève n'est pas prise en compte.

class Horaire(models.Model):
    classe = models.CharField(max_length=20)
    jour = models.CharField(max_length=10)  # Lundi, Mardi...
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    matiere = models.CharField(max_length=50)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE)
    annee_academique = models.CharField(max_length=20)

class Presence(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE)
    classe = models.CharField(max_length=100)
    date = models.DateField(auto_now_add=True)
    etat = models.CharField(max_length=20, choices=[('present', 'Présent'), ('absent', 'Absent')])
    horaire = models.ForeignKey(Horaire, on_delete=models.SET_NULL, null=True, blank=True)
    motif = models.CharField(max_length=255, blank=True, null=True)
