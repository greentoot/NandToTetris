# Nand Asset Studio

Atelier Python local pour convertir des images en assets **Nand2Tetris**, générer
du Jack/VM et essayer les programmes dans un exécuteur intégré. Interface Tkinter
sombre, aperçu pixelisé agrandissable, réglages en direct et guide inclus.

## Interface et réactivité

- Export toujours accessible en bas du panneau de réglages ; **Ctrl+O** pour
  importer, **Ctrl+E** pour exporter.
- Vues **Original**, **Résultat** et **Comparer** côte à côte.
- Zoom ajusté ou **100 / 200 / 400 %**, avec défilement du canevas.
- Vignettes cliquables, lecture/pause et cadence d'animation réglable de 1 à 30 images/s.
- Enregistrement et chargement des réglages JSON ; copie du code complet.
- Conversion et génération du code en arrière-plan. Seule la demande la plus
  récente est conservée en attente ; un résultat périmé ne remplace pas le nouvel aperçu.
- Aperçus et vignettes en cache ; un écran d'émulateur inchangé n'est pas redessiné.
- Le CPU/VM cède régulièrement la main pour garder le clavier et les boutons réactifs.
- Des séparateurs à glisser permettent de redimensionner les panneaux de réglages,
  le canevas, le code, l'écran de l'exécuteur et ses diagnostics. **Disposition**
  rétablit les proportions initiales. La fenêtre principale et l'éditeur sont
  redimensionnables indépendamment.

Les opérations vidéo, la suppression de fond et la trame Bayer utilisent les
opérations natives Pillow. [Mesures avant/après](PERFORMANCE.md), reproductibles
avec `python benchmark.py`. Les facteurs sont des mesures locales de ces opérations,
pas une promesse de vitesse globale ou de FPS dans tous les jeux.

## Retoucher et rouvrir un artwork

Après conversion, cliquer sur **Retoucher**. Une fenêtre indépendante propose :

- Crayon noir/blanc, taille réglable ; gomme **Transparent** pour les sprites.
- Remplissage, pipette, zoom jusqu'à 1600 % et grille visible à fort zoom.
- Navigation entre les images d'une animation, annuler/rétablir (**Ctrl+Z / Ctrl+Y**).
- Export PNG de l'image en cours.

**Appliquer au projet** transmet les retouches au canevas, au code généré et aux
prochains exports CPU/Jack/VM. Les retouches ne modifient jamais le fichier image
source. Si les réglages sont recalculés aux mêmes dimensions, elles sont réappliquées
par-dessus le résultat. Si les dimensions changent, les retouches de l'ancien format
restent en mémoire et se réappliquent en revenant à ces dimensions. Importer une
nouvelle source commence un nouveau document sans ces retouches.

**Sauver artwork** ou **Ctrl+S** enregistre un fichier **.nandart** : image source,
réglages, toutes les images et leurs retouches. L'historique annuler/rétablir reste
propre à la session d'édition et n'est pas enregistré dans le projet.
**Rouvrir un artwork…** recharge un `.nandart`, ou le fichier **asset.json** d'un
projet déjà exporté. Pour cet ancien export, les PNG générés servent de nouvelle
source, puisque la photo originale n'y est pas stockée.

Les retouches en cours dans l'éditeur doivent être appliquées avant de sauvegarder
le projet principal. Si la source est changée pendant l'édition, l'application
refuse de remplacer la nouvelle source par les anciennes retouches ; l'éditeur
permet toujours d'enregistrer son image en PNG.

## Démarrer

Python **3.10 ou plus récent**, Tkinter et Pillow sont nécessaires.
Sur Windows, Tkinter accompagne normalement l'installation Python officielle.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Sous Windows : double-cliquer **Lancer.bat**. `start.pyw` lance l'interface sans
console lorsque Python et Pillow sont déjà installés. Aucun compte, abonnement,
service réseau ou clé API n'est nécessaire. Le code et les dépendances du
compilateur sont inclus ; le dossier peut être déplacé hors du dépôt d'origine.
Les PNG d'exemple sont de petits dessins génériques générés par `make_examples.py`.

Pour l'onglet **Vidéo**, FFmpeg (5 ou plus récent) doit être installé séparément
et accessible dans le PATH. Sinon, le bouton **Choisir FFmpeg…** permet de sélectionner
son exécutable. FFprobe, s'il est présent à côté ou dans le PATH, fournit la durée
et les dimensions. L'atelier image fonctionne aussi sans ces exécutables.

## Vidéo : traitement rapide et local

### Ajouter et supprimer des frames

Dans **Atelier** et **Vidéo**, les boutons sous la lecture permettent de
**Ajouter des frames**, **Supprimer la frame** sélectionnée et **Annuler frames**
(la dernière modification de séquence). L'import accepte plusieurs fichiers
image et les insère dans l'ordre de sélection, après l'image active. Les images
sont ajustées aux dimensions de la séquence puis converties en noir et blanc
avec les réglages courants. Une séquence garde au moins une frame.

Dans l'atelier, les retouches existantes sont conservées, et l'ajout/suppression
persiste après une reconversion ou la réouverture du `.nandart`. Limite :
256 frames. Dans Vidéo, on peut aussi démarrer une séquence directement avec
des images, sans FFmpeg ; limite : 4096 frames. Le lecteur, les exports et
le prochain **Tester sur CPU Hack** utilisent la séquence modifiée.

### Importer une vidéo

L'onglet **02 Vidéo** importe MP4, MOV, MKV, AVI, WEBM, GIF et les formats que votre
FFmpeg sait décoder. Le fichier reste sur votre machine : aucun upload réseau.

1. **Importer une vidéo**, puis choisir le début et la durée de l'extrait.
2. Choisir **Rapide** (256 × 128, 8 images/s) ou **Nand complet** (512 × 256, 12 images/s).
   Une résolution de 128 × 64 et une cadence de 1 à 30 images/s sont aussi proposées.
3. Régler seuil, contraste, inversion, cadrage et éventuellement trame Bayer.
4. **Traiter l'extrait** : progression, annulation, interface disponible pendant le travail.
5. Lire le résultat, avancer image par image ou utiliser la barre de défilement.

Le décodage, la sélection temporelle, le redimensionnement et le seuil rapide
s'exécutent dans FFmpeg. Python reçoit une image grise à la fois et stocke les
images finales en **1 bit**, sans conserver le film en RGBA. Le lecteur ne garde
que quelques aperçus agrandis en cache et suit le temps réel en sautant des images
si la machine ne suffit pas à toutes les afficher. La conversion complète des films
longs n'est pas déclenchée implicitement : les extraits sont limités à 120 secondes
et 4096 images. La vidéo n'a pas d'audio.

Les [mesures vidéo](VIDEO_PERFORMANCE.md) utilisent une source HD synthétique ;
`python benchmark_video.py` permet de reproduire le test sur votre machine.

### Exports et retouches vidéo

**Tester sur CPU Hack** envoie l'extrait traité dans l'exécuteur, à partir de
l'image sélectionnée. Exécuter, Pause, Pas à pas et Réinitialiser fonctionnent.
Les petites résolutions sont agrandies en pixels nets à 512 × 256.
Le Studio fournit chaque image dans un tampon RAM ordinaire (16 à 8207) ;
une ROM Hack fixe copie ces mots dans SCREEN et signale la fin via RAM[0].
Toutes les écritures écran sont exécutées par le CPU. La séquence boucle sans
sauter d'image, à une cadence limitée par le CPU et le réglage de vitesse.
Ce mode utilise un flux externe fourni par le Studio : il ne produit pas un
programme vidéo autonome pour l'émulateur officiel. Le `.nandvideo` reste
un conteneur d'assets.

- **.nandvideo** : conteneur ZIP rapide, manifeste JSON et images à 1 bit dans
  `frames.bin`. Il se rouvre directement dans l'onglet Vidéo, sans redécodage.
- **MP4 / GIF** : vidéo monochrome consultable dans un lecteur ordinaire, encodée
  en arrière-plan par FFmpeg. Le MP4 est compressé avec H.264 ; le conteneur
  `.nandvideo` conserve exactement les images binaires.
- **Image → atelier** : retoucher et exporter l'image courante.
- **Séquence → atelier** : importer jusqu'à 120 images comme une planche, avec
  cadence d'aperçu conservée. Toutes les images peuvent ensuite être retouchées,
  sauvegardées en `.nandart` et exportées en Jack/VM. Une longue séquence génère
  beaucoup de code et son export sera plus lent que l'enregistrement `.nandvideo`.

Le conteneur `.nandvideo` est un **format d'assets**, pas une vidéo lisible nativement
par le CPU Hack. Les contraintes de ROM et la vitesse du VM restent applicables
aux projets exportés ; le Main Jack de démonstration affiche la première image.
Un moteur de jeu doit appeler les différentes images et gérer leur cadence.

Le format binaire contient `width*height/8` octets par image, lignes de haut en bas,
bit fort à gauche et 1 = blanc. Python/Pillow le lit avec
`Image.frombytes('1', (width, height), frame_bytes)`. La disposition mémoire Hack
est différente ; le générateur de l'atelier effectue cette conversion pour les exports.

## Atelier

- Images PNG/JPG/GIF/BMP/WEBP. Pour un GIF importé, la première image est utilisée.
- Écran 512 × 256 : contenir avec marges, remplir par recadrage ou étirer.
- Sprite : taille native, transparence, agrandissement entier de 1 à 8.
- Planche : cellules régulières de largeur/hauteur réglables, ordre gauche-droite
  puis haut-bas ; aperçu animé. Les cellules incomplètes en bordure sont ignorées.
- Seuil, contraste, inversion, trame Floyd–Steinberg ou Bayer 4 × 4.
- Suppression d'une couleur avec tolérance ou des deux couleurs dominantes d'un
  damier peint. Les pixels alpha sont conservés et seuillés à 128.
- Aperçus du Jack, de l'ASM et du manifeste JSON.

Le bouton d'export crée un dossier neuf horodaté et un ZIP à côté. Il contient
les sources Jack, les VM compilées, les huit classes système, les PNG des images,
un GIF pour les planches, un aperçu 512 × 256, un manifeste et un guide.
Un programme ASM/HACK indépendant affiche la première image centrée.

### Réutiliser un asset

Pour un écran :

```java
do Artwork.draw();
```

Pour un sprite ou une planche :

```java
do Artwork.draw(x, y, frame);
```

L'index commence à zéro. Les coordonnées peuvent être négatives : l'affichage
est limité aux bords de l'écran. Le masque permet de conserver le décor sous les
pixels transparents ; **le jeu doit restaurer l'ancienne position** avant de déplacer
le sprite. Le Main exporté affiche la première image, pas un moteur de jeu complet.
Le rendu d'écran écrit des mots vidéo de 16 bits ; les sprites utilisent des
segments de pixels. La taille du code et la vitesse varient selon la complexité.

## Exécuteur intégré

### CPU Hack

« Tester sur CPU Hack » assemble l'image courante puis exécute réellement les
instructions. Le chargeur accepte aussi des `.asm` et `.hack` externes.
L'assembleur et le CPU couvrent l'ALU Hack, les destinations simultanées, les sauts,
la ROM, la RAM, l'écran et le clavier. La cadence dépend de Python et de la machine.

La ROM a une limite de **32 768 instructions**. Si un export dépasse cette limite,
le diagnostic est conservé et le `.hack` n'est pas produit ; le Jack/VM reste
exporté. L'ASM d'image fixe est généré directement : il ne représente pas la
traduction d'un jeu Jack entier.

### VM pédagogique

Charger un dossier de classes `.vm`, ou utiliser **Compiler Jack** sur un dossier
de sources. La compilation utilise un dossier temporaire et conserve les sources
d'origine. `final.vm` est ignoré pour éviter de dupliquer les classes.

L'entrée est `Sys.init` si présente, sinon `Main.main`. Les instructions VM,
segments, appels, variables statiques et retours sont interprétés. Screen,
Memory, Array, Keyboard, Math et certains appels Output/Sys utilisent des
adaptateurs Python. Les fonctions restantes, notamment String, sont exécutées
depuis les classes chargées. Les appels inconnus produisent une erreur.

Ce n'est **pas l'émulateur officiel**. Les adaptateurs système, la police,
la représentation interne des piles et la cadence diffèrent du système officiel.
Les projets utilisant les adresses des structures internes de pile VM peuvent
donc ne pas être compatibles. Les programmes exportés doivent aussi être validés
dans les outils officiels pour une remise de projet.

Run, Pause, Reset et Pas à pas sont disponibles. Cliquer sur l'écran pour capturer
le clavier ; **Échap** libère la capture. Le registre clavier ne contient qu'une
touche à la fois, comme sur Hack. Les `Sys.wait` ne bloquent pas l'interface.

## Architecture

- `core.py` : conversion, découpe, générateurs Jack/ASM et export portable.
- `machines.py` : assembleur, CPU, VM et framebuffer.
- `compiler.py` : intégration du compilateur fourni dans ce dépôt.
- `app.py` : interface et orchestration réactive.
- `ui_features.py` : aperçu comparatif, zoom, vignettes, caches et réglages.
- `jobs.py` : tâches de fond avec suppression des demandes intermédiaires.
- `artwork.py` : document modifiable, historique et archives `.nandart`.
- `editor.py`, `artwork_ui.py` : éditeur de pixels et actions sur le projet.
- `video.py`, `video_ui.py` : flux FFmpeg, stockage 1 bit, lecteur et exports vidéo.
- `video_cpu.py` : lecteur CPU Hack avec tampon RAM alimenté par le Studio.
- `vendor/jack` : compilateur du groupe 8, adapté pour remonter les erreurs.
- `vendor/os` : classes système VM provenant du projet du groupe 8.
- `test_studio.py` : tests de référence CPU, export, compilation, masques et VM.

## Vérifier

Depuis le dossier de l'application :

```powershell
python -m unittest -v
```

Les tests couvrent chaque opération ALU avec plusieurs destinations et sauts,
l'ordre des bits vidéo, les masques et débordements de sprites, le découpage,
les trames, les appels VM, le clavier, les attentes et un export Jack/VM/CPU complet.
Un essai d'intégration d'un prototype Hollow Knight local a également validé l'intro,
le passage par Entrée, le chargement du décor et le déplacement dans cet exécuteur.

Le compilateur Jack et les VM système sont conservés avec leur provenance dans
`THIRD_PARTY.md`. Cette livraison n'ajoute pas de licence à ces composants tiers.
