# Maison Alliance — e-commerce d'alliances en or

Site Django + Stripe d'alliances en or premium, au **prix indexé sur le cours spot de l'or**.

## Fonctionnalités

| Besoin | Où |
|---|---|
| Page d'accueil | `apps/core` — `/` |
| Catalogues homme / femme (les modèles « mixte » apparaissent dans les deux), filtres couleur/titre/profil, tri par prix | `apps/catalog` — `/alliances/homme/`, `/alliances/femme/` |
| Fiche produit avec détail du calcul du prix par taille | `/alliances/<slug>/` |
| Blog SEO / GEO : chapô, encadré « À retenir », FAQ, JSON-LD (BlogPosting, FAQPage, BreadcrumbList), RSS | `apps/blog` — `/journal/` |
| Page « Comment ça fonctionne » (parcours client en 5 étapes, JSON-LD HowTo + FAQ) | `apps/core` — `/comment-ca-fonctionne/` |
| Coffret d'essai de 4 alliances factices (stock géré), 100 € : 20 € remboursés au retour, 80 € déduits de la commande | `apps/trialkit` — `/coffret-essai/` |
| Indexation des prix sur le cours de l'or | `apps/pricing` — `/cours-de-l-or/` |
| Panier, paiement Stripe Checkout, webhook | `apps/orders` |
| SEO technique : `sitemap.xml`, `robots.txt`, canonical, Open Graph, JSON-LD Product/Organization | `apps/core` |
| GEO (moteurs IA) : `/llms.txt` généré dynamiquement (catalogue, prix, FAQ) | `apps/core` |

## Structure des produits

La fiche produit reprend le format d'une fiche joaillerie : galerie, sélecteurs **Métal / Type de pierre / Poids carat / Taille**, gravure, commentaire, date de livraison, onglets **Description / Détails / Écrin**, « Existe aussi en », avis, « Dans la même collection », certificat, FAQ et réassurance.

| Table (admin) | Rôle |
|---|---|
| **Bijou** (`Ring`) | La fiche : catégorie (alliance, solitaire, bague), genre, pierre centrale, textes des onglets, délai de fabrication, poids d'or de référence, façon, marge |
| **Métal** | Couleurs d'or du sélecteur « Métal » (or jaune, blanc, rose…), avec pastille. Tous les métaux d'un bijou ont le même titre (18 ct), donc le même prix |
| **Option de pierre** | Une ligne par couple *type de pierre × poids carat* (ex. diamant naturel 0,50 ct), avec son coût d'achat HT |
| **Photo** | Galerie, éventuellement propre à un métal |
| **Collection** | « Dans la même collection » et pages `/alliances/collection/<slug>/` |
| **Famille de modèle** | Déclinaisons d'un même dessin avec d'autres pierres (« Existe aussi en ») |
| **Écrin** | Contenu de l'onglet « Écrin » |
| **Avis client** | Avis de la boutique (ou d'un produit). N'afficher que de vrais avis |
| **Question fréquente (fiches produit)** et **Bloc de réassurance** | Sections communes à toutes les fiches |

Prix d'une variante : `[poids d'or selon la taille × titre × cours du jour × (1 + prime) + façon + petites pierres + coût de la pierre choisie] × (1 + marge) × 1,20`. Seul l'or suit le cours.

## Administration et tâches

L'admin (`/admin/`) a un thème clair/sombre épuré et un **tableau de bord** : boutons **Tâches du jour** et **Tâches de la semaine** (7 prochains jours), commandes à traiter, coffrets à expédier, chiffre d'affaires du mois et cours de l'or.

La liste des tâches (`/admin/taches/`) réunit :
- les **tâches manuelles** (ajout rapide en haut de la page, ou table « Tâches ») ;
- les **tâches automatiques**, qui disparaissent d'elles-mêmes une fois traitées :
  - coffret payé → *préparer et expédier* (sous 24 h), avec bon d'envoi et étiquette retour ;
  - coffret chez le client → *réceptionner le retour* (date limite = livraison + 8 jours, en rouge si dépassée) ;
  - coffret reçu → *contrôler et rembourser 20 €* ;
  - relances de retour à envoyer ;
  - commande payée → *lancer la fabrication*, puis *expédier* avant la date de livraison promise ;
  - cours de l'or périmé → *mettre à jour le cours*.

Chaque tâche a un bouton d'action rapide (« Marquer expédié », « Passer en fabrication », « Terminer »…). Les tâches en retard apparaissent en rouge, en tête de liste.

## Parcours client et coffret d'essai

1. Le client choisit **4 alliances factices** (modèles d'essai, miroirs des vraies alliances en or), paie **100 €** et saisit ses coordonnées et son adresse (Stripe Checkout, ou page de paiement simulée en mode démo).
2. **E-mail de confirmation** : contenu du coffret, adresse, délai de retour et code unique `ESSAI-XXXX-XXXX`.
3. Le coffret apparaît dans le **tableau de bord** (« Préparer et expédier le coffret ») avec les **références des factices** à mettre dans le kit.
4. **Bon d'envoi** (liste de préparation + adresses + code-barres) et **étiquette retour** (adresse de l'atelier, référence en code-barres) générés automatiquement, imprimables depuis la tâche ou la fiche du coffret.
5. Le client a **8 jours après la livraison** pour renvoyer le coffret (livraison = date saisie, ou expédition + 2 jours).
6. **E-mail à l'expédition** (suivi, date limite, lien vers l'étiquette retour), puis **relance tous les 2 jours** jusqu'au retour (`python manage.py send_kit_reminders`, à planifier chaque jour ; aussi déclenchable depuis les tâches).
7. Coffret reçu → « Reçu, à contrôler » → **« Valider et rembourser »** : remboursement de **20 €** via Stripe (simulé en mode démo) et e-mail au client.

Les **80 €** restants sont déduits de la commande d'alliances avec le code unique ; sans commande, ils ne sont pas remboursés. Tous les montants et délais se règlent dans `.env` (`TRIAL_KIT_*`).

### Stock des factices

Table **Alliances factices (stock)** : référence du factice, vraie alliance représentée, taille, exemplaires possédés. Un factice est indisponible à la sélection quand tous ses exemplaires sont pris : coffrets en cours de paiement (30 min), à préparer, expédiés, livrés ou reçus mais pas encore contrôlés. Les vraies alliances n'ont pas de stock (fabrication à la commande). Le bouton « Essayer à domicile » d'une fiche produit n'apparaît que si un factice est disponible.

### E-mails

Sans configuration, les e-mails s'affichent dans le terminal du serveur. Pour les envoyer réellement, renseigner `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` et `DEFAULT_FROM_EMAIL` (Brevo, Mailjet, Gmail…). Chaque envoi est consultable dans l'admin (**E-mails envoyés**).

## Calcul du prix

Le prix de vente n'est **jamais saisi** : il est recalculé à partir du dernier cours enregistré.

```
poids (taille T)  = poids de référence × T / taille de référence   (la taille FR correspond au tour de doigt en mm)
or fin            = poids × titre (750 ‰ pour l'or 18 carats)
coût              = or fin × cours €/g × (1 + prime métal) + façon + pierres
prix HT           = coût × (1 + marge)
prix TTC          = prix HT × 1,20, arrondi à l'euro supérieur
```

Garde-fous :
- **Cours périmé** (plus vieux que `GOLD_PRICE_MAX_AGE_MINUTES`) : les paiements sont suspendus.
- **Variation suspecte** (> 15 % par rapport au cours précédent) : la cotation est rejetée (`--force` pour l'accepter).
- **Prix figé au paiement** : la commande enregistre le cours et les prix unitaires ; la session Stripe expire au bout de 30 minutes.

Fournisseurs (`GOLD_PRICE_PROVIDER`) :
- `goldapi` : [goldapi.io](https://www.goldapi.io), clé requise, cotation directe en EUR (recommandé en production) ;
- `goldapicom` : [gold-api.com](https://gold-api.com) (gratuit, USD) converti en EUR au taux BCE via frankfurter.app ;
- `manual` : saisie du cours dans l'admin.

## Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # renseigner les clés
python manage.py migrate
python manage.py seed_demo      # 12 alliances, 2 articles, un cours de démonstration
python manage.py createsuperuser
python manage.py runserver
```

Cours de l'or : planifier `python manage.py update_gold_price` (cron toutes les 15 min, par exemple).

### Mode démo des paiements (par défaut)

Tant qu'aucune clé Stripe n'est configurée (`STRIPE_DEMO_MODE=1`), le bouton de paiement mène à une page de paiement **simulée** sur le site : on saisit ses coordonnées, on clique sur « Payer » et la commande ou le coffret passe en « Payé », sans débit. Un bandeau signale ce mode sur tout le site. Cela permet de faire tout le parcours :

1. `/coffret-essai/` : choisir 4 alliances, payer 100 € en démo et noter le code `ESSAI-XXXX-XXXX` ;
2. ajouter une alliance au panier, saisir le code (−80 €) et payer en démo ;
3. vérifier la commande et le coffret (« Converti en commande ») dans `/admin/`.

Le mode démo est refusé au démarrage si une clé `sk_live_` est configurée. Pour passer sur Stripe : `STRIPE_DEMO_MODE=0` et renseigner les clés (`sk_test_…` d'abord, carte de test `4242 4242 4242 4242`).

Webhook Stripe en local :

```bash
stripe listen --forward-to localhost:8000/stripe/webhook/
```

Événements traités : `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`.

## Tests

```bash
python manage.py test
```

## Prochaines étapes suggérées

- Photos produits (champ `image`) et visuels éditoriaux ;
- Étiquettes transporteur affranchies et suivi automatique de livraison (API Colissimo, Boxtal ou Sendcloud) ;
- Comptes clients ;
- PostgreSQL, stockage S3 des médias et cache Redis en production ;
- Textes légaux (CGV, mentions légales) à compléter.
