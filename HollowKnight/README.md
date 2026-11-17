# Hollow Knight — Silksong : trois zones reliées

Prototype Jack pour le VM Emulator de Nand2Tetris, écran noir et blanc 512 × 256.

## Lancer et jouer

Charger le dossier **HollowKnight/VM** dans le VM Emulator,
lancer Run avec l'animation désactivée et activer la capture clavier.
Le logo Silksong apparaît en premier. Appuyer sur **Entrée**, puis relâcher pour jouer.

- **Gauche / droite** : marcher en maintenant la touche.
- **Espace ou haut** : sauter ; relâcher avant un nouveau saut.
- **X** (ou **Z**) : attaque à l'aiguille, relâcher avant la suivante.
- Continuer jusqu'au bord **gauche** pour passer à la zone suivante.
- Revenir au bord **droit** pour retrouver la zone précédente.
- Stop dans l'émulateur pour arrêter.

Le clavier standard de Nand2Tetris ne fournit qu'une touche à la fois : déclencher
le saut, puis maintenir une direction pour se déplacer en l'air.

## Parcours

1. **Grotte de la cage** : décor précédent et Hornet mobile.
2. **Passage des plateformes**, à gauche : corniches latérales, sol inférieur
   et plateforme centrale. Les plateformes permettent de passer à travers par
   dessous puis d'atterrir dessus. La hauteur du saut permet d'atteindre le centre.
3. **Arène des cocons**, encore à gauche : boss inspiré de la capture fournie,
   avec masque, yeux noirs, couronne, abdomen segmenté et ailes animées.
   Le boss flotte à droite ; on peut explorer l'arène et repartir.

Les deux extrémités du parcours sont fermées. Le passage d'une zone à l'autre
recentre le personnage à l'entrée et le pose sur une surface sûre.
L'aiguille inflige un dégât au boss si elle le touche pendant le coup.
Le boss flotte en hauteur : sauter puis appuyer sur X à sa portée.
Il clignote après un impact et disparaît après huit coups. Sa défaite reste
acquise si l'on quitte puis revient dans l'arène. Le boss ne riposte pas encore ;
il n'y a pas encore de dégâts subis par Hornet ni d'écran de victoire.
Le HUD, la cage et les cocons sont décoratifs.

## Graphismes

Les trois décors sont des adaptations simplifiées des captures, réalisées avec
l'outil intégré **imagegen**, puis converties en bitmaps strictement noir et blanc.
Les prompts des nouveaux décors sont conservés dans `assets/crossing-prompt.txt`
et `assets/arena-prompt.txt`. Les captures sources et les illustrations sont incluses.
La notification Windows de la référence n'est pas reproduite dans l'arène.
Les plateformes et le sol utilisent des surfaces de collision horizontales adaptées
aux dessins ; leurs contours végétaux restent approximatifs.
Hornet utilise la planche de sprites fournie (`assets/hornet-sheet.png`), importée
en noir et blanc par `hornet_frames.py` avec suppression exacte des deux couleurs
du damier. Douze poses : deux de repos, quatre de marche, montée, descente et quatre
phases d'attaque. Les animations avancent avec le temps et suivent la direction.
La position de la tête et des pieds est alignée entre les poses. Le boss reste
défini par géométrie dans `generate_sprite.py`, avec deux poses.
L'attaque dure environ 480 ms de délais programmés (la vitesse réelle dépend de
l'émulateur), immobilise la marche pendant son exécution et ne frappe qu'une fois.
La barre de vie en haut à gauche reprend exactement les mêmes pixels de la
première grotte dans les trois zones. Elle reste fixe pendant cette version.
Hornet regarde à droite en allant à droite et à gauche en allant à gauche.

## Sources et vérification

- `Main.jack` : logo et attente d'Entrée.
- `Game.jack` : zones, clavier, gravité, plateformes, animations et dégâts de l'aiguille.
- `Title.jack`, `Scene.jack`, `Crossing.jack`, `Arena.jack` : écrans générés.
- `Sprite.jack`, `Boss.jack` : sprites générés et affichage masqué.
- `hornet_frames.py` : cellules de la planche et import monochrome de Hornet.
- `VM/` : huit classes du jeu compilées et huit classes système, prêtes à charger.

Une seule copie du décor (8192 mots) est réutilisée dans toutes les zones.
Pendant le déplacement, seules les anciennes zones des sprites sont restaurées ;
le boss et Hornet sont ensuite redessinés dans cet ordre, y compris s'ils se superposent.
Aucune nouvelle allocation n'est nécessaire pendant la marche, les attaques ou
les transitions. Seule la pose courante de Hornet est chargée en RAM, pour éviter
de stocker simultanément les 24 images des deux directions.

Pour reconstruire depuis la racine du dépôt, avec Python 3.10+ et Pillow :

```powershell
python -m pip install -r NandStudio/requirements.txt
python HollowKnight/build.py
```

Le script régénère les classes Jack graphiques à partir des images et compile les
huit classes du jeu avec le compilateur inclus dans `NandStudio`. Il copie aussi
les huit classes système dans `VM/`. Les aperçus livrés dans `previews/` ont été
produits lors de la vérification de la version d'origine ; cette reconstruction
ne relance pas ses tests d'exécution.

Le dossier `VM/` contient les classes individuelles et le système ; ne pas ajouter
un agrégat `final.vm`, qui dupliquerait les fonctions.
La cible livrée est le VM Emulator ; les performances interactives et le CPU Hack
standard restent à valider dans les outils officiels.
