"""Page « comment ca marche », servie a cote du questionnaire.

Une demonstration de triage ne se defend pas toute seule : celui qui la
regarde doit pouvoir savoir ce qui decide, ce qui est mesure, et ou le modele
intervient -- sans lire le code ni le rapport. Cette page repond a ces
questions la ou elles se posent, dans l'interface elle-meme.

Meme parti pris que la page de demonstration : une constante Python, aucune
ressource externe, aucun script tiers.
"""

from __future__ import annotations

from typing import Final

PAGE_EXPLICATIONS: Final[str] = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comment ça marche — Aide au triage CHSA</title>
<style>
  :root {
    --encre: #16202a; --gris: #5b6b7a; --trait: #dfe5ea; --fond: #f4f6f8;
    --carte: #fff; --accent: #2a78d6; --max: #c0392b; --mod: #d98016;
    --dif: #2e8b57; --alerte: #fdf3f2;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --encre: #e8edf2; --gris: #9aa8b5; --trait: #2b3641; --fond: #12181e;
      --carte: #1a222b; --accent: #5ba3f5; --max: #f0705f; --mod: #f0a94a;
      --dif: #5fc48a; --alerte: #2a1d1c;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0 1rem 4rem;
    font: 15px/1.6 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--encre); background: var(--fond);
  }
  main { max-width: 760px; margin: 0 auto; }
  header { padding: 2.2rem 0 1rem; }
  h1 { font-size: 1.5rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
  h2 {
    font-size: 1.08rem; margin: 0 0 .7rem; letter-spacing: -.005em;
    padding-bottom: .5rem; border-bottom: 1px solid var(--trait);
  }
  h3 { font-size: .95rem; margin: 1.2rem 0 .4rem; }
  .sous { color: var(--gris); margin: 0; font-size: .93rem; }
  .carte {
    background: var(--carte); border: 1px solid var(--trait);
    border-radius: 8px; padding: 1.3rem; margin-bottom: 1rem;
  }
  p { margin: 0 0 .8rem; }
  ul, ol { margin: 0 0 .8rem; padding-left: 1.2rem; }
  li { margin-bottom: .35rem; }
  code {
    background: var(--fond); padding: 1px 5px; border-radius: 3px;
    font-size: .88em; border: 1px solid var(--trait);
  }
  .cadre-table { overflow-x: auto; margin: 0 0 .8rem; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  th {
    text-align: left; font-weight: 600; padding: .4rem .6rem;
    border-bottom: 2px solid var(--trait); white-space: nowrap;
  }
  td { padding: .4rem .6rem; border-bottom: 1px solid var(--trait); vertical-align: top; }
  .sommaire { font-size: .9rem; }
  .sommaire ol { columns: 2; column-gap: 2rem; padding-left: 1.1rem; }
  .sommaire a { color: var(--accent); text-decoration: none; }
  .sommaire a:hover { text-decoration: underline; }
  .avert {
    padding: .7rem .9rem; background: var(--alerte);
    border-left: 3px solid var(--max); border-radius: 0 4px 4px 0;
    font-size: .88rem; margin: 0 0 .8rem;
  }
  .note {
    padding: .7rem .9rem; background: var(--fond);
    border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0;
    font-size: .88rem; margin: .8rem 0;
  }
  .flux { list-style: none; padding: 0; margin: 0 0 .8rem; counter-reset: etape; }
  .flux li {
    position: relative; padding: .5rem 0 .5rem 2.2rem;
    border-bottom: 1px solid var(--trait);
  }
  .flux li:last-child { border-bottom: none; }
  .flux li::before {
    counter-increment: etape; content: counter(etape);
    position: absolute; left: 0; top: .55rem;
    width: 1.5rem; height: 1.5rem; border-radius: 50%;
    background: var(--accent); color: #fff;
    font-size: .78rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
  }
  .etiq {
    display: inline-block; padding: .1rem .5rem; border-radius: 999px;
    font-size: .75rem; font-weight: 700; color: #fff; letter-spacing: .03em;
  }
  .e-regles { background: var(--dif); }
  .e-modele { background: var(--accent); }
  .e-garde  { background: var(--mod); }
  .pied { text-align: center; font-size: .85rem; color: var(--gris); margin-top: 1.6rem; }
  .pied a, .retour a { color: var(--accent); }
  .retour { font-size: .9rem; margin-bottom: 1rem; }
</style>
</head>
<body>
<main>
  <header>
    <p class="retour"><a href="/">← retour au questionnaire</a></p>
    <h1>Comment ça marche</h1>
    <p class="sous">
      Ce que fait ce service, dans quel ordre, et qui décide à chaque étape.
    </p>
  </header>

  <div class="carte sommaire">
    <ol>
      <li><a href="#front">En quoi est écrite cette interface</a></li>
      <li><a href="#relie">À quoi elle est reliée</a></li>
      <li><a href="#questions">D'où viennent les questions</a></li>
      <li><a href="#reponse">Ce qui se passe à chaque réponse</a></li>
      <li><a href="#adaptatif">Ce qui rend le questionnaire adaptatif</a></li>
      <li><a href="#resultat">Comment le résultat est construit</a></li>
      <li><a href="#justesse">Comment on s'assure qu'il est juste</a></li>
      <li><a href="#modele">Où le modèle intervient — et où il n'intervient pas</a></li>
    </ol>
  </div>

  <section class="carte" id="front">
    <h2>1 · En quoi est écrite cette interface</h2>
    <p>
      HTML, CSS et JavaScript natifs. <strong>Aucun cadriciel, aucune
      bibliothèque, aucune ressource chargée depuis un tiers</strong> : pas de
      React, pas de jQuery, pas de police distante, pas de réseau de diffusion
      de contenu. Ce que votre navigateur exécute tient entièrement dans la page
      qu'il a reçue.
    </p>
    <p>
      La page est une constante Python, servie par l'API elle-même à l'adresse
      racine. Deux raisons, et aucune n'est esthétique :
    </p>
    <ul>
      <li>
        L'image déployée n'embarque que les sources Python du paquet. Un fichier
        statique posé à côté risquerait de ne pas suivre au déploiement — une
        panne qui n'apparaîtrait qu'en production.
      </li>
      <li>
        Un service de santé ne doit pas faire dépendre son interface de la
        disponibilité d'un tiers, ni laisser fuiter vers lui l'adresse des
        postes qui consultent.
      </li>
    </ul>
  </section>

  <section class="carte" id="relie">
    <h2>2 · À quoi elle est reliée</h2>
    <p>
      La page appelle l'API du même domaine avec <code>fetch()</code>, en
      joignant la clé d'accès dans l'en-tête HTTP <code>X-Cle-Api</code>. Elle
      n'utilise que trois routes :
    </p>
    <div class="cadre-table">
    <table>
      <tr><th>Appel</th><th>Ce qu'il fait</th></tr>
      <tr>
        <td><code>POST /entretiens</code></td>
        <td>Ouvre un entretien, renvoie son identifiant et la première question</td>
      </tr>
      <tr>
        <td><code>POST /entretiens/{session}/reponses</code></td>
        <td>Enregistre une réponse, renvoie la question suivante ou le triage</td>
      </tr>
      <tr>
        <td><code>GET /audit/{session}</code></td>
        <td>Relit la trace complète de l'entretien, affichée en bas du résultat</td>
      </tr>
    </table>
    </div>
    <p>Derrière ces trois routes :</p>
    <div class="cadre-table">
    <table>
      <tr><th>Couche</th><th>Technologie</th><th>Rôle</th></tr>
      <tr>
        <td>API</td><td>FastAPI, servie par uvicorn</td>
        <td>Valide les entrées, orchestre l'entretien, journalise</td>
      </tr>
      <tr>
        <td>Inférence</td><td>vLLM, sur processeur graphique</td>
        <td>Sert le modèle de langage spécialisé</td>
      </tr>
      <tr>
        <td>Modèle</td><td>Qwen3-1.7B-Base + adaptateur LoRA</td>
        <td>67 Mo appris sur le triage, posés sur un modèle de base public</td>
      </tr>
      <tr>
        <td>Barème</td><td>Python, règles explicites</td>
        <td>Recalcule le niveau sans le modèle</td>
      </tr>
      <tr>
        <td>Journal</td><td>Fichier JSONL chaîné, sur disque persistant</td>
        <td>Consigne chaque événement, empreinte à empreinte</td>
      </tr>
      <tr>
        <td>Hébergement</td><td>Conteneur Docker sur GPU, à la demande</td>
        <td>S'éteint après cinq minutes sans trafic</td>
      </tr>
    </table>
    </div>
    <div class="note">
      <strong>Le champ <code>moteur</code> de chaque réponse dit qui a
      répondu.</strong> <code>vllm</code> : le modèle. <code>regles</code> : le
      barème seul, sans modèle — le mode utilisé en local et en intégration
      continue, où il n'y a pas de carte graphique. Le repli existe, mais il
      n'est jamais silencieux : un service qui répondrait par le barème en
      laissant croire que le modèle a parlé fausserait à la fois les mesures et
      la lecture clinique.
    </div>
  </section>

  <section class="carte" id="questions">
    <h2>3 · D'où viennent les questions</h2>
    <p>
      Elles ne sont pas importées d'un référentiel officiel : elles sont écrites
      dans le code, et <strong>chacune existe parce qu'une règle de tri en a
      besoin</strong>. Une question à laquelle aucun critère ne se raccroche
      ferait perdre du temps à l'accueil sans jamais changer le niveau.
    </p>
    <h3>Les constantes demandées</h3>
    <p>
      Score de Glasgow, saturation, fréquence respiratoire, pression systolique,
      fréquence cardiaque, température, douleur. Ce sont les sept paramètres sur
      lesquels le barème porte un seuil. Elles sont posées dans l'ordre de leur
      pouvoir de décision : une saturation à 86 % conclut à elle seule, une
      douleur à 3 sur 10 n'exclut jamais rien.
    </p>
    <h3>Les signes de gravité dépistés</h3>
    <p>
      Ils viennent de douze présentations décrites dans le code — douleur
      thoracique, dyspnée, déficit neurologique brutal, douleur abdominale,
      traumatisme d'un membre, fièvre, malaise avec perte de connaissance,
      céphalée, lombalgie, réaction allergique, plaie superficielle,
      vomissements et diarrhée. Chacune porte ses propres signes d'alerte.
      Quand le motif saisi ne correspond à aucune d'elles, trois signes
      généraux servent de repli : troubles de la vigilance, difficulté à parler
      ou à respirer, douleur d'intensité brutale et inhabituelle.
    </p>
    <h3>Le barème</h3>
    <p>
      Il s'agit d'une <strong>transposition simplifiée de l'échelle de tri
      française FRENCH</strong>, ramenée aux trois niveaux demandés par le CHSA
      (urgence maximale, urgence modérée, prise en charge différée).
    </p>
    <div class="avert">
      <strong>Ce barème n'a pas été validé par un clinicien.</strong> C'est la
      limite structurante de cette preuve de concept, et elle est assumée dans
      le rapport. Le même barème a servi à produire les étiquettes du jeu
      d'entraînement : s'il est faux quelque part, le modèle a appris cette
      erreur, et l'évaluation ne peut pas la voir. Un pilote hospitalier
      commencerait par faire relire ces seuils.
    </div>
  </section>

  <section class="carte" id="reponse">
    <h2>4 · Ce qui se passe à chaque réponse</h2>
    <p>
      Le navigateur poste un couple <code>{cle, valeur}</code> — la valeur
      toujours sous forme de chaîne, y compris pour un nombre. Ensuite, dans cet
      ordre :
    </p>
    <ol class="flux">
      <li>
        <strong>L'entretien est retrouvé</strong> par son identifiant de session.
        Inconnu ou déjà clôturé, la réponse est <code>404</code>.
      </li>
      <li>
        <strong>La valeur est convertie et vérifiée.</strong> Hors bornes ou
        illisible, elle est refusée en <code>422</code>, avec un message qui
        nomme le champ et la borne — de quoi corriger la saisie sans deviner.
      </li>
      <li>
        <strong>La réponse est consignée au journal</strong>
        (<code>reponse_recue</code>), avec l'empreinte de l'entrée précédente.
      </li>
      <li>
        <strong>La question suivante est recalculée depuis zéro</strong> sur
        l'état courant de l'entretien. Rien n'est mémorisé d'un tour à l'autre :
        le même dossier donne toujours la même suite de questions.
      </li>
      <li>
        <strong>Ou bien le recueil s'arrête</strong> et le triage est déclenché.
      </li>
    </ol>
    <div class="note">
      Si la clé envoyée n'est pas celle de la question posée, le service
      <strong>ne proteste pas et repose la même question</strong>. C'est
      délibéré : un entretien de triage ne doit pas avancer sur une réponse qui
      ne correspond pas à ce qui a été demandé.
    </div>
  </section>

  <section class="carte" id="adaptatif">
    <h2>5 · Ce qui rend le questionnaire adaptatif</h2>
    <p>Deux mécanismes, tous deux entièrement déterministes.</p>
    <h3>Le motif choisit ce qu'on dépiste</h3>
    <p>
      On ne cherche pas les mêmes signes chez un patient venu pour une douleur
      thoracique — irradiation au bras gauche, douleur au repos, pâleur,
      malaise — et chez un patient venu pour une entorse. Le motif saisi
      sélectionne la liste des signes d'alerte présentés.
    </p>
    <h3>Le recueil s'arrête dès qu'il ne peut plus rien changer</h3>
    <p>
      Après chaque constante enregistrée, le barème est rejoué en entier. Dès
      qu'un critère d'urgence maximale est rempli, <strong>les questions
      suivantes ne peuvent plus modifier le niveau</strong> : elles ne
      feraient que retarder la prise en charge. Le questionnaire s'arrête.
    </p>
    <div class="cadre-table">
    <table>
      <tr><th>Dossier</th><th>Questions posées</th><th>Niveau rendu</th></tr>
      <tr>
        <td>Douleur thoracique, signe de gravité présent</td>
        <td><strong>4</strong></td><td>Urgence maximale</td>
      </tr>
      <tr>
        <td>Mal de gorge, aucun signe, constantes normales</td>
        <td><strong>12</strong></td><td>Prise en charge différée</td>
      </tr>
    </table>
    </div>
    <div class="note">
      <strong>Ces deux décisions ne sont jamais confiées au modèle.</strong>
      Un modèle de langage qui déciderait lui-même du moment où l'on cesse
      d'interroger un patient pourrait conclure sur un dossier vide. C'est la
      panne la plus dangereuse qu'un dispositif d'aide au triage puisse avoir,
      et la règle d'arrêt est écrite pour qu'elle soit impossible.
    </div>
  </section>

  <section class="carte" id="resultat">
    <h2>6 · Comment le résultat est construit</h2>
    <p>Trois objets distincts interviennent, dans cet ordre :</p>
    <div class="cadre-table">
    <table>
      <tr><th></th><th>Ce que c'est</th><th>Ce qu'il produit</th></tr>
      <tr>
        <td><span class="etiq e-regles">BARÈME</span></td>
        <td>Des seuils écrits à la main, rejoués sur les constantes</td>
        <td><code>niveau_regles</code> et la liste des <code>criteres</code></td>
      </tr>
      <tr>
        <td><span class="etiq e-modele">MODÈLE</span></td>
        <td>Le modèle spécialisé, interrogé une seule fois</td>
        <td><code>niveau_modele</code> et l'explication en langage naturel</td>
      </tr>
      <tr>
        <td><span class="etiq e-garde">GARDE-FOU</span></td>
        <td>Une fonction d'arbitrage entre les deux</td>
        <td><code>niveau</code> — celui qui est servi — et <code>escalade</code></td>
      </tr>
    </table>
    </div>
    <h3>La règle d'arbitrage tient en une phrase</h3>
    <p><strong>Le plus grave des deux niveaux l'emporte.</strong></p>
    <ul>
      <li>
        Le modèle annonce <em>moins</em> grave que le barème : la priorité est
        relevée, <code>escalade</code> passe à vrai, et l'écart est consigné au
        journal.
      </li>
      <li>
        Le modèle annonce <em>plus</em> grave : sa prudence est conservée.
      </li>
      <li>
        Le modèle ne rend aucun niveau lisible — réponse tronquée, format
        inattendu : le barème tranche seul, et l'écart est signalé. Rendre
        « indéterminé » à un agent d'accueil serait la pire des sorties.
      </li>
    </ul>
    <div class="note">
      <strong>Pourquoi ce dispositif existe.</strong> Sur 600 cas de contrôle
      portant des motifs jamais vus à l'entraînement, le modèle annonce
      <strong>17 urgences vitales sur 200 à un niveau moindre</strong>, soit
      8,5 % de sous-triage critique. Un service qui servirait le modèle seul
      enverrait ces 17 patients en salle d'attente. C'est la raison pour
      laquelle le modèle n'est jamais servi seul — et la raison pour laquelle
      son désaccord avec le barème est affiché plutôt que masqué.
    </div>
  </section>

  <section class="carte" id="justesse">
    <h2>7 · Comment on s'assure qu'il est juste</h2>
    <h3>Ce qui est vérifié automatiquement</h3>
    <ul>
      <li>
        Plus de 200 tests unitaires, rejoués à chaque modification du code.
        Les seuils du barème y sont testés <em>à la borne exacte</em> — c'est
        là que se cachent les erreurs de tri.
      </li>
      <li>
        Vingt contrôles supplémentaires portent sur les données livrées :
        empreintes des jeux, seuil de données personnelles résiduelles, et
        absence de patient présent à la fois à l'entraînement et au test. Une
        fuite entre les deux invaliderait tous les chiffres sans provoquer la
        moindre erreur de code.
      </li>
      <li>
        Après chaque déploiement, une campagne mesure sur le service réel la
        latence, la robustesse et l'intégrité de la chaîne d'audit.
      </li>
    </ul>
    <h3>Ce qui a été mesuré sur le modèle</h3>
    <div class="cadre-table">
    <table>
      <tr><th>Jeu de contrôle</th><th>Exactitude</th><th>Sous-triage critique</th></tr>
      <tr>
        <td>99 cas, motifs vus à l'entraînement</td>
        <td>92,9 %</td><td>0 urgence vitale manquée</td>
      </tr>
      <tr>
        <td>600 cas, 14 motifs <em>jamais vus</em></td>
        <td>90,2 % [87,5 à 92,3]</td>
        <td><strong>8,5 % [5,4 à 13,2]</strong></td>
      </tr>
    </table>
    </div>
    <h3>Ce que vous pouvez vérifier vous-même</h3>
    <ul>
      <li>
        Le résultat affiche <em>les deux</em> niveaux, celui du modèle et celui
        du barème, ainsi que les critères objectifs retenus. Un désaccord se
        voit.
      </li>
      <li>
        La trace d'audit, dépliable sous chaque résultat, rejoue l'entretien
        question par question.
      </li>
      <li>
        <a href="/audit">L'intégrité du journal</a> se contrôle à tout moment :
        chaque entrée porte l'empreinte de la précédente, si bien qu'une
        modification, une suppression, une insertion ou un réordonnancement
        cassent la chaîne et sont signalés.
      </li>
    </ul>
    <div class="avert">
      <strong>« Juste » veut dire ici « conforme au barème », pas « conforme à
      la vérité clinique ».</strong> Le barème n'ayant pas été validé par un
      clinicien, aucun chiffre de cette page ne mesure une qualité médicale :
      ils mesurent la fidélité du système à ses propres règles. La décision de
      triage reste celle du personnel soignant.
    </div>
  </section>

  <section class="carte" id="modele">
    <h2>8 · Où le modèle intervient — et où il n'intervient pas</h2>
    <p>
      Le modèle est interrogé <strong>une seule fois par entretien</strong>, à
      la toute fin, quand le recueil est déjà complet. Il reçoit le tableau
      clinique mis en forme exactement comme à l'entraînement — la même
      fonction produit les deux, de sorte qu'aucune dérive de format n'est
      possible entre ce qui a été appris et ce qui est servi. Il rend un texte,
      dont le niveau est extrait.
    </p>
    <div class="cadre-table">
    <table>
      <tr><th>Étape</th><th>Qui décide</th></tr>
      <tr><td>Quelles questions poser, et dans quel ordre</td>
          <td><span class="etiq e-regles">BARÈME</span> code déterministe</td></tr>
      <tr><td>Quels signes de gravité dépister</td>
          <td><span class="etiq e-regles">BARÈME</span> d'après le motif</td></tr>
      <tr><td>Quand cesser d'interroger</td>
          <td><span class="etiq e-regles">BARÈME</span> règle d'arrêt</td></tr>
      <tr><td>Si une saisie est acceptable</td>
          <td><span class="etiq e-regles">BARÈME</span> bornes de validation</td></tr>
      <tr><td>Quels critères objectifs sont retenus</td>
          <td><span class="etiq e-regles">BARÈME</span> seuils explicites</td></tr>
      <tr><td>Le niveau proposé et son explication rédigée</td>
          <td><span class="etiq e-modele">MODÈLE</span></td></tr>
      <tr><td>Le niveau finalement servi</td>
          <td><span class="etiq e-garde">GARDE-FOU</span> le plus grave des deux</td></tr>
    </table>
    </div>
    <p>
      Autrement dit : le modèle apporte la <strong>formulation</strong> et un
      <strong>second avis</strong>. Il ne conduit pas l'entretien, et son avis
      ne peut jamais faire baisser une priorité — seulement la maintenir ou
      la relever.
    </p>
  </section>

  <section class="carte">
    <h2>Ce que ce service ne fait pas</h2>
    <div class="avert">
      <strong>Ce n'est pas un dispositif médical.</strong> Aucun diagnostic,
      aucune prescription, aucune décision autonome.
    </div>
    <ul>
      <li>
        <strong>Adultes uniquement.</strong> Le barème et le modèle n'ont été
        construits et mesurés que sur des adultes.
      </li>
      <li>
        <strong>Le barème ignore le terrain du patient.</strong> Une saturation
        de 92 % chez un insuffisant respiratoire chronique peut être sa valeur
        de base ; elle sera pourtant classée en urgence modérée. Le système
        sur-trie plutôt que de sous-trier, mais il sur-trie.
      </li>
      <li>
        <strong>Les entretiens en cours vivent en mémoire.</strong> Un
        redémarrage du service les perd. Les entretiens terminés, eux, sont au
        journal, qui est sur disque persistant.
      </li>
      <li>
        <strong>Le journal garantit l'intégrité, pas la confidentialité.</strong>
        Il prouve qu'un enregistrement n'a pas été modifié après coup ; il
        n'empêche personne d'y accéder de le lire.
      </li>
      <li>
        <strong>Une clé unique et partagée protège le service.</strong> Pas de
        rôles, pas d'expiration, aucune trace nominative de qui a appelé.
        Suffisant pour une preuve de concept, insuffisant pour un pilote
        hospitalier.
      </li>
      <li>
        <strong>N'y saisissez aucune donnée de patient réel.</strong>
      </li>
    </ul>
  </section>

  <p class="pied">
    <a href="/">questionnaire</a>
    · <a href="/docs">documentation de l'API</a>
    · <a href="/openapi.json">schéma OpenAPI</a>
    · <a href="/audit">intégrité du journal</a>
  </p>
</main>
</body>
</html>
"""
