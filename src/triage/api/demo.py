"""Page de demonstration servie a la racine du service.

Le cahier des charges demande « une interface de demonstration fonctionnelle ».
L'API seule y repond sur le papier, mais elle ne se montre pas : une soutenance
ou un essai par une equipe soignante ont besoin d'une page qui deroule le
questionnaire et affiche le resultat.

Le gabarit est une constante Python plutot qu'un fichier a cote : l'image
deployee n'embarque que les sources Python du paquet, et un fichier statique
risquerait de ne pas suivre -- panne qui n'apparaitrait qu'en production.

La page n'appelle aucune ressource externe. Un service de sante ne doit pas
faire dependre son interface d'un tiers, et le conteneur n'a de toute facon
aucune raison d'avoir acces a un reseau de diffusion de contenu.
"""

from __future__ import annotations

from typing import Final

PAGE: Final[str] = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aide au triage — CHSA</title>
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
    font: 15px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--encre); background: var(--fond);
  }
  main { max-width: 720px; margin: 0 auto; }
  header { padding: 2.2rem 0 1.2rem; }
  h1 { font-size: 1.5rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
  .sous { color: var(--gris); margin: 0; font-size: .93rem; }
  .avert {
    margin: 1.1rem 0 0; padding: .7rem .9rem; background: var(--alerte);
    border-left: 3px solid var(--max); border-radius: 0 4px 4px 0;
    font-size: .85rem; color: var(--encre);
  }
  .carte {
    background: var(--carte); border: 1px solid var(--trait);
    border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem;
  }
  label { display: block; font-weight: 600; margin-bottom: .45rem; font-size: .93rem; }
  .aide { font-weight: 400; color: var(--gris); font-size: .85rem; }
  input, select, button {
    font: inherit; padding: .55rem .7rem; border-radius: 6px;
    border: 1px solid var(--trait); background: var(--carte); color: var(--encre);
  }
  input, select { width: 100%; }
  input:focus, select:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  button {
    background: var(--accent); color: #fff; border: none; cursor: pointer;
    font-weight: 600; padding: .6rem 1.1rem;
  }
  button:hover:not(:disabled) { filter: brightness(1.08); }
  button:disabled { opacity: .5; cursor: default; }
  button.discret {
    background: transparent; color: var(--accent);
    padding: .4rem 0; font-weight: 500;
  }
  .rangee { display: flex; gap: .6rem; align-items: flex-end; margin-top: .9rem; }
  .rangee > :first-child { flex: 1; }
  .oui-non { display: flex; gap: .6rem; }
  .oui-non button { flex: 1; }
  .progression { font-size: .82rem; color: var(--gris); margin-bottom: .8rem; }
  .niveau {
    display: inline-block; padding: .3rem .8rem; border-radius: 999px;
    color: #fff; font-weight: 700; font-size: .82rem; letter-spacing: .04em;
  }
  .maximale { background: var(--max); }
  .moderee  { background: var(--mod); }
  .differee { background: var(--dif); }
  .criteres { margin: .9rem 0 0; padding-left: 1.1rem; }
  .criteres li { margin-bottom: .2rem; }
  pre {
    white-space: pre-wrap; background: var(--fond); padding: .8rem;
    border-radius: 6px; font-size: .87rem; margin: .9rem 0 0;
    border: 1px solid var(--trait);
  }
  .meta { font-size: .8rem; color: var(--gris); margin-top: .9rem; }
  .meta code { background: var(--fond); padding: 1px 5px; border-radius: 3px; }
  .escalade {
    margin-top: .9rem; padding: .6rem .8rem; background: var(--alerte);
    border-left: 3px solid var(--mod); border-radius: 0 4px 4px 0; font-size: .87rem;
  }
  .attente { color: var(--gris); font-size: .9rem; }
  .erreur { color: var(--max); font-size: .9rem; }
  details { margin-top: .9rem; }
  summary { cursor: pointer; font-size: .87rem; color: var(--accent); }
  table { width: 100%; border-collapse: collapse; font-size: .8rem; margin-top: .6rem; }
  td { padding: 3px 6px; border-bottom: 1px solid var(--trait); vertical-align: top; }
  td:first-child { color: var(--gris); white-space: nowrap; width: 5.5rem; }
  .pied { text-align: center; font-size: .8rem; color: var(--gris); margin-top: 1.6rem; }
  .pied a { color: var(--accent); }
  .point {
    display: inline-block; width: 7px; height: 7px;
    border-radius: 50%; margin-right: .4rem;
  }
  .vert { background: var(--dif); } .orange { background: var(--mod); }
</style>
</head>
<body>
<main>
  <header>
    <h1>Aide au triage aux urgences</h1>
    <p class="sous">Centre Hospitalier Saint-Aurélien — preuve de concept</p>
    <div class="avert">
      <strong>Ce n'est pas un dispositif médical.</strong> Aucun diagnostic, aucune
      prescription, aucune décision autonome. Le barème est une transposition
      simplifiée de l'échelle FRENCH, <strong>non validée par un clinicien</strong>.
      Adulte uniquement. N'y saisissez aucune donnée de patient réel.
    </div>
  </header>

  <div class="carte" id="carte-cle">
    <label for="cle">Clé d'accès
      <span class="aide">— l'endpoint est protégé ; la clé reste dans cet onglet</span>
    </label>
    <div class="rangee">
      <input type="password" id="cle" autocomplete="off" placeholder="X-Cle-Api">
      <button id="valider-cle">Entrer</button>
    </div>
    <p class="erreur" id="erreur-cle" hidden></p>
  </div>

  <div class="carte" id="carte-entretien" hidden>
    <p class="progression" id="progression"></p>
    <div id="zone-question"></div>
    <p class="attente" id="attente" hidden></p>
    <p class="erreur" id="erreur" hidden></p>
  </div>

  <div class="carte" id="carte-resultat" hidden>
    <span class="niveau" id="badge"></span>
    <ul class="criteres" id="criteres"></ul>
    <div class="escalade" id="escalade" hidden></div>
    <pre id="explication"></pre>
    <p class="meta" id="meta"></p>
    <details id="details-audit">
      <summary>Trace d'audit de cet entretien</summary>
      <table id="audit"></table>
    </details>
    <button class="discret" id="recommencer">↻ Nouvel entretien</button>
  </div>

  <p class="pied">
    <span class="point vert" id="voyant"></span><span id="etat-service">service</span>
    · <a href="/docs">documentation de l'API</a>
    · <a href="/openapi.json">schéma OpenAPI</a>
  </p>
</main>

<script>
const $ = (id) => document.getElementById(id);
let cle = sessionStorage.getItem("cle_triage") || "";
let session = null;

const enteteJson = () => ({ "Content-Type": "application/json", "X-Cle-Api": cle });

// Le conteneur s'éteint après cinq minutes d'inactivité : le premier appel le
// rallume et peut demander deux minutes. Sans message, l'attente ressemble à
// une panne.
async function appeler(chemin, options = {}) {
  const debut = performance.now();
  const lent = setTimeout(() => {
    $("attente").hidden = false;
    $("attente").textContent =
      "Réveil du serveur en cours… le conteneur s'éteint après cinq minutes " +
      "d'inactivité, le premier appel peut demander jusqu'à deux minutes.";
    $("voyant").className = "point orange";
    $("etat-service").textContent = "démarrage à froid";
  }, 2500);
  try {
    const r = await fetch(chemin, options);
    if (r.status === 401) throw new Error("Clé d'accès refusée.");
    if (!r.ok) {
      const corps = await r.json().catch(() => ({}));
      throw new Error(corps.detail || `Erreur ${r.status}`);
    }
    return await r.json();
  } finally {
    clearTimeout(lent);
    $("attente").hidden = true;
    $("voyant").className = "point vert";
    $("etat-service").textContent =
      `service · ${Math.round(performance.now() - debut)} ms`;
  }
}

function afficherErreur(message) {
  $("erreur").hidden = false;
  $("erreur").textContent = message;
}

function champPour(q) {
  if (q.type_reponse === "oui_non") {
    return `<div class="oui-non">
        <button data-valeur="oui">Oui</button>
        <button data-valeur="non">Non</button>
      </div>`;
  }
  if (q.type_reponse === "choix") {
    const options = q.options.map((o) => `<option>${o}</option>`).join("");
    return `<div class="rangee"><select id="saisie">${options}</select>
      <button id="envoyer">Suivant</button></div>`;
  }
  const type = q.type_reponse === "texte" ? "text" : "number";
  const pas = q.type_reponse === "decimal" ? ' step="0.1"' : "";
  const bornes =
    q.minimum !== null && q.minimum !== undefined
      ? ` min="${q.minimum}" max="${q.maximum}"`
      : "";
  return `<div class="rangee">
      <input id="saisie" type="${type}"${pas}${bornes} autocomplete="off">
      <button id="envoyer">Suivant</button>
    </div>`;
}

function afficherQuestion(etat) {
  const q = etat.question;
  const unite = q.unite ? ` <span class="aide">(${q.unite})</span>` : "";
  const bornes =
    q.minimum !== null && q.minimum !== undefined && q.type_reponse !== "choix"
      ? ` <span class="aide">— entre ${q.minimum} et ${q.maximum}</span>`
      : "";
  $("progression").textContent =
    `Question ${etat.questions_posees + 1} · le recueil s'arrête dès qu'un ` +
    `critère d'urgence maximale est rempli`;
  $("zone-question").innerHTML =
    `<label>${q.libelle}${unite}${bornes}</label>` + champPour(q);
  $("erreur").hidden = true;

  const envoyer = (valeur) => repondre(q.cle, valeur);
  if (q.type_reponse === "oui_non") {
    $("zone-question")
      .querySelectorAll("button")
      .forEach((b) => (b.onclick = () => envoyer(b.dataset.valeur)));
  } else {
    const saisie = $("saisie");
    $("envoyer").onclick = () => envoyer(saisie.value);
    saisie.onkeydown = (e) => { if (e.key === "Enter") envoyer(saisie.value); };
    saisie.focus();
  }
}

async function repondre(cleQuestion, valeur) {
  if (!String(valeur).trim()) return afficherErreur("Une réponse est attendue.");
  $("zone-question").querySelectorAll("button, input, select")
    .forEach((e) => (e.disabled = true));
  try {
    const etat = await appeler(`/entretiens/${session}/reponses`, {
      method: "POST",
      headers: enteteJson(),
      body: JSON.stringify({ cle: cleQuestion, valeur: String(valeur) }),
    });
    etat.termine ? afficherResultat(etat) : afficherQuestion(etat);
  } catch (e) {
    afficherErreur(e.message);
    $("zone-question").querySelectorAll("button, input, select")
      .forEach((el) => (el.disabled = false));
  }
}

const LIBELLES = {
  maximale: "URGENCE MAXIMALE",
  moderee: "URGENCE MODÉRÉE",
  differee: "PRISE EN CHARGE DIFFÉRÉE",
};

async function afficherResultat(etat) {
  const t = etat.triage;
  $("carte-entretien").hidden = true;
  $("carte-resultat").hidden = false;
  $("badge").className = "niveau " + t.niveau;
  $("badge").textContent = LIBELLES[t.niveau];
  $("criteres").innerHTML = t.criteres.length
    ? t.criteres.map((c) => `<li>${c}</li>`).join("")
    : "<li>aucun critère de gravité retenu</li>";
  $("explication").textContent = t.explication;

  // Le desaccord entre le modele et le bareme n'est jamais masque : c'est
  // une information clinique, pas un detail d'implementation.
  if (t.escalade) {
    $("escalade").hidden = false;
    $("escalade").innerHTML =
      `<strong>Priorité relevée par le garde-fou.</strong> Le modèle annonçait ` +
      `« ${LIBELLES[t.niveau_modele] || "aucun niveau exploitable"} », le barème ` +
      `« ${LIBELLES[t.niveau_regles]} ». Le plus grave des deux l'emporte.`;
  } else {
    $("escalade").hidden = true;
  }

  $("meta").innerHTML =
    `${etat.questions_posees} questions posées · ` +
    `latence <code>${t.latence_ms} ms</code> · ` +
    `moteur <code>${t.moteur}</code> · modèle <code>${t.modele}</code>`;

  try {
    const trace = await appeler(`/audit/${session}`, { headers: enteteJson() });
    $("audit").innerHTML = trace
      .map((e) => {
        const detail = e.contenu.cle || e.contenu.niveau || "";
        return `<tr><td>${e.horodatage.slice(11, 19)}</td>
                <td>${e.evenement}</td><td>${detail}</td></tr>`;
      })
      .join("");
  } catch {
    $("details-audit").hidden = true;
  }
}

async function demarrer() {
  $("carte-cle").hidden = true;
  $("carte-resultat").hidden = true;
  $("carte-entretien").hidden = false;
  $("zone-question").innerHTML = "";
  $("progression").textContent = "Ouverture de l'entretien…";
  try {
    const etat = await appeler("/entretiens", {
      method: "POST",
      headers: enteteJson(),
      body: JSON.stringify({ langue: "fr" }),
    });
    session = etat.session;
    afficherQuestion(etat);
  } catch (e) {
    if (e.message.includes("Clé")) {
      sessionStorage.removeItem("cle_triage");
      cle = "";
      $("carte-entretien").hidden = true;
      $("carte-cle").hidden = false;
      $("erreur-cle").hidden = false;
      $("erreur-cle").textContent = e.message;
      return;
    }
    afficherErreur(e.message);
  }
}

$("valider-cle").onclick = () => {
  cle = $("cle").value.trim();
  sessionStorage.setItem("cle_triage", cle);
  demarrer();
};
$("cle").onkeydown = (e) => { if (e.key === "Enter") $("valider-cle").click(); };
$("recommencer").onclick = demarrer;

if (cle) demarrer();
</script>
</body>
</html>
"""
