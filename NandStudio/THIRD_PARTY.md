# Provenance

`vendor/jack` contient une copie du compilateur Jack du projet du groupe 8 :
`Jack/generator.py`, `Parser.py`, `Lexer.py`, `Reader.py`, `todot.py`.
Le README d'origine crédite le groupe 8 : Anthony, Ethan, Enzo et Julien.
La copie du parseur remonte une exception exploitable dans l'interface plutôt
que d'arrêter le programme ; le compilateur reste un compilateur pédagogique.

`vendor/os` contient les huit VM système du projet du groupe 8,
copiées depuis `Jack/jeu/ZeldaLike` : Array, Keyboard, Math, Memory, Output,
Screen, String, Sys. Aucun fichier tiers n'est téléchargé par cette application.

Pillow est une dépendance installée séparément et conserve sa propre licence.
Python et Tk/Tkinter conservent leurs licences respectives.

FFmpeg et FFprobe sont des exécutables externes optionnels pour l'onglet vidéo.
Ils ne sont pas inclus dans ce paquet et conservent leurs licences et configurations
de compilation propres. Le Studio les invoque localement, sans les télécharger.

Les exemples de cette livraison sont des dessins génériques créés par le code
de `make_examples.py`. Aucun asset Hollow Knight n'est inclus dans ce paquet.

Aucune licence du dépôt d'origine n'a été ajoutée ou remplacée dans cette livraison.
