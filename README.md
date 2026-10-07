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
| Coffret d'essai de 8 à 12 alliances, vendu 80 € par Stripe, avec code unique de déduction | `apps/trialkit` — `/coffret-essai/` |
| Indexation des prix sur le cours de l'or | `apps/pricing` — `/cours-de-l-or/` |
| Panier, paiement Stripe Checkout, webhook | `apps/orders` |
| SEO technique : `sitemap.xml`, `robots.txt`, canonical, Open Graph, JSON-LD Product/Organization | `apps/core` |
| GEO (moteurs IA) : `/llms.txt` généré dynamiquement (catalogue, prix, FAQ) | `apps/core` |

## Parcours client et coffret d'essai

1. Le client commande le coffret d'essai (80 €, `TRIAL_KIT_PRICE_CENTS`) : un code unique `ESSAI-XXXX-XXXX` lui est remis sur la page de confirmation.
2. Il essaie les alliances chez lui.
3. Il renvoie le coffret.
4. Il commande ses alliances et saisit le code dans le panier : le prix du coffret est déduit (coupon Stripe à usage unique).
5. Il reçoit ses alliances.

Sans commande d'alliances, le prix du coffret n'est pas remboursé. Le code n'est actif qu'une fois le coffret payé, il ne sert qu'une fois, et il est réservé 30 minutes pendant un paiement en cours. Quand la commande est payée, le coffret passe automatiquement au statut « Converti en commande ».

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

1. `/coffret-essai/` : choisir 8 à 12 alliances, payer 80 € en démo et noter le code `ESSAI-XXXX-XXXX` ;
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
- E-mails transactionnels (confirmation de commande, expédition du coffret) ;
- Envoi du code de coffret par e-mail (aujourd'hui affiché sur la page de confirmation et dans l'admin) ;
- Comptes clients ;
- PostgreSQL, stockage S3 des médias et cache Redis en production ;
- Textes légaux (CGV, mentions légales) à compléter.
