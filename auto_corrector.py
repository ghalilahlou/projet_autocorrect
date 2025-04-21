import tkinter as tk
from tkinter import ttk, messagebox
import difflib
from collections import Counter
from nltk.tokenize import word_tokenize
import threading
import nltk
import math

# Téléchargement automatique des ressources nécessaires
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/gutenberg')
except LookupError:
    nltk.download('gutenberg')

# Fonction de chargement du corpus en fonction de la langue
def load_corpus(lang="en"):
    if lang == "en":
        from nltk.corpus import gutenberg
        texte = gutenberg.raw('austen-emma.txt')
    elif lang == "fr":
        with open("corpus_fr.txt", "r", encoding="utf-8") as f:
            texte = f.read()
    else:
        raise ValueError("Langue non supportée.")
    return texte

# Fonction de construction du vocabulaire à partir du corpus
def build_vocabulary(texte, language="en"):
    # Définir le tokenizer en fonction de la langue
    tokenizer_lang = "english" if language == "en" else "french"
    try:
        tokens = word_tokenize(texte.lower(), language=tokenizer_lang)
    except LookupError:
        # Fallback : découpage par espaces
        tokens = texte.lower().split()
    mots = [mot for mot in tokens if mot.isalpha()]
    return set(mots), Counter(mots)

# Fonction avancée de génération des candidats
def generate_candidates_advanced(word, vocabulary, frequencies, n=3):
    # On récupère plus de candidats que le nombre voulu
    candidates = difflib.get_close_matches(word, vocabulary, n=10, cutoff=0.5)
    scored = []
    for cand in candidates:
        # Calcul du ratio de similarité
        sim = difflib.SequenceMatcher(None, word, cand).ratio()
        # On utilise la fréquence (minimale 1 pour éviter log(0))
        freq = frequencies.get(cand, 1)
        score = sim * (1 + math.log(freq))
        scored.append((cand, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_candidates = [cand for cand, score in scored][:n]
    if not top_candidates:
        top_candidates = [word]
    return top_candidates

# Application Tkinter enrichie
class AutoCorrectApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔤 Correcteur Interactif NLP")
        self.root.geometry("950x650")
        self.root.resizable(False, False)

        # Dictionnaires pour stocker le vocabulaire et les fréquences selon la langue
        self.vocabulaire = {}
        self.frequences = {}
        self.suggestion_vars = []  # Stocke les StringVar pour chaque mot
        self.history = []          # Historique des corrections

        self.build_gui()
        # Par défaut, on charge le corpus anglais
        self.auto_load_corpus("en")

    def build_gui(self):
        # Cadre supérieur avec choix de langue et boutons d'action
        top_frame = ttk.Frame(self.root)
        top_frame.pack(pady=10)

        ttk.Label(top_frame, text="Langue :").pack(side="left", padx=5)
        self.language = tk.StringVar(value="en")
        self.language_menu = ttk.OptionMenu(top_frame, self.language, "en", "en", "fr", command=self.auto_load_corpus)
        self.language_menu.pack(side="left", padx=5)

        # Changement de couleur du statut selon la langue
        self.status_label = ttk.Label(top_frame, text="Chargement du corpus...", foreground="blue")
        self.status_label.pack(side="left", padx=20)

        # Boutons pour Effacer et Exporter
        self.clear_button = ttk.Button(top_frame, text="Effacer le texte", command=self.clear_input)
        self.clear_button.pack(side="left", padx=5)
        self.export_button = ttk.Button(top_frame, text="Exporter correction", command=self.export_correction)
        self.export_button.pack(side="left", padx=5)

        # Zone de saisie du texte
        self.text_input = tk.Text(self.root, width=90, height=7, font=("Arial", 13))
        self.text_input.pack(pady=10)

        # Option d'auto-correction en temps réel
        self.auto_correct = tk.BooleanVar(value=False)
        auto_check = ttk.Checkbutton(self.root, text="Auto-correction en temps réel", variable=self.auto_correct)
        auto_check.pack(pady=5)
        self.after_id = None
        self.text_input.bind("<KeyRelease>", self.on_text_change)

        # Bouton pour générer les suggestions manuellement
        self.correct_button = ttk.Button(self.root, text="🔧 Proposer des corrections", command=self.corriger_interactivement)
        self.correct_button.pack(pady=5)

        # Cadre scrollable pour les suggestions interactives
        self.scroll_canvas = tk.Canvas(self.root, borderwidth=0)
        self.scroll_frame = ttk.Frame(self.scroll_canvas)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scroll_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas_frame = self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')
        self.scroll_frame.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

        # Bouton de confirmation
        self.confirm_button = ttk.Button(self.root, text="✅ Confirmer les choix", command=self.confirmer_correction)
        self.confirm_button.pack(pady=10)

        # Zone de résultat final
        self.result_label = ttk.Label(self.root, text="", wraplength=800, font=("Arial", 12), foreground="green")
        self.result_label.pack(pady=5)

        # Cadre pour l'historique des corrections avec bouton de réinitialisation
        history_frame = ttk.LabelFrame(self.root, text="Historique des corrections")
        history_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.history_list = tk.Listbox(history_frame, height=6, font=("Arial", 11))
        self.history_list.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_list.yview)
        self.history_list.configure(yscrollcommand=history_scrollbar.set)
        history_scrollbar.pack(side="right", fill="y")
        self.reset_history_button = ttk.Button(history_frame, text="Réinitialiser l'historique", command=self.reset_history)
        self.reset_history_button.pack(side="bottom", pady=5)

    def auto_load_corpus(self, lang):
        def run():
            # Modification du thème en fonction de la langue
            if lang == "en":
                self.status_label.config(foreground="blue")
            else:
                self.status_label.config(foreground="purple")
            self.status_label.config(text="Chargement du corpus...", foreground="orange")
            texte = load_corpus(lang)
            self.vocabulaire[lang], self.frequences[lang] = build_vocabulary(texte, language=lang)
            self.status_label.config(text=f"✔ Corpus {lang.upper()} chargé ({len(self.vocabulaire[lang])} mots)", foreground=("blue" if lang == "en" else "purple"))
        threading.Thread(target=run).start()

    def corriger_interactivement(self):
        # Vide le cadre des suggestions et réinitialise la liste
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.suggestion_vars.clear()

        phrase = self.text_input.get("1.0", "end").strip()
        lang = self.language.get()
        try:
            tokens = word_tokenize(phrase.lower(), language="english" if lang == "en" else "french")
        except LookupError:
            tokens = phrase.lower().split()

        # Parcours de chaque mot pour créer une ligne de suggestion
        for mot in tokens:
            frame = ttk.Frame(self.scroll_frame, padding=5)
            frame.pack(fill="x", pady=3)
            ttk.Label(frame, text=f"Mot : '{mot}'", width=20).pack(side="left", padx=5)
            var = tk.StringVar(frame)
            if mot.isalpha() and mot not in self.vocabulaire[lang]:
                # Génération avancée des suggestions
                candidats = generate_candidates_advanced(mot, self.vocabulaire[lang], self.frequences[lang], n=3)
                # Création d'options contenant à la fois le mot et son score de similarité
                options = []
                for cand in candidats:
                    score = difflib.SequenceMatcher(None, mot, cand).ratio()
                    options.append(f"{cand} (score: {score:.2f})")
                var.set(options[0])
                option_menu = ttk.OptionMenu(frame, var, options[0], *options)
                option_menu.pack(side="left", padx=10)
            else:
                var.set(mot)
                ttk.Label(frame, text="(Mot valide)").pack(side="left", padx=10)
            self.suggestion_vars.append(var)

    def confirmer_correction(self):
        # Extrait la correction finale en retirant les scores affichés
        corrected = []
        for var in self.suggestion_vars:
            val = var.get()
            if " (score:" in val:
                val = val.split(" (score:")[0]
            corrected.append(val)
        phrase_corrigée = " ".join(corrected)
        self.result_label.config(text=f"🟢 Texte corrigé :\n{phrase_corrigée}")
        # Copier le texte corrigé dans le presse-papiers
        self.root.clipboard_clear()
        self.root.clipboard_append(phrase_corrigée)
        self.root.update()
        # Ajout à l'historique
        self.history.append(phrase_corrigée)
        self.history_list.insert(tk.END, phrase_corrigée)

    def clear_input(self):
        # Efface la zone de saisie et les suggestions, et réinitialise le résultat
        self.text_input.delete("1.0", tk.END)
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.suggestion_vars.clear()
        self.result_label.config(text="")

    def export_correction(self):
        # Exporte le texte corrigé visible dans la zone résultat dans un fichier texte
        texte_export = self.result_label.cget("text")
        if texte_export:
            try:
                with open("correction_export.txt", "w", encoding="utf-8") as f:
                    f.write(texte_export)
                messagebox.showinfo("Export", "La correction a été exportée dans 'correction_export.txt'.")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de l'export : {e}")
        else:
            messagebox.showwarning("Aucun texte", "Aucune correction à exporter.")

    def reset_history(self):
        # Réinitialise l'historique des corrections
        self.history.clear()
        self.history_list.delete(0, tk.END)

    def on_text_change(self, event=None):
        # Si l'auto-correction est activée, planifie la mise à jour des suggestions
        if self.auto_correct.get():
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = self.root.after(500, self.corriger_interactivement)

# Lancement de l'application
if __name__ == "__main__":
    root = tk.Tk()
    app = AutoCorrectApp(root)
    root.mainloop()
