const state = { step: 0, characters: [], scenes: [], plan: null };
const steps = ["basics", "characters", "scenes", "review"];

function requestId(prefix) { return `${prefix}-${Date.now()}`; }
function qs(id) { return document.getElementById(id); }
function setStatus(text) { const node = qs("status"); if (node) node.textContent = text; }
function showStep(index) {
  state.step = Math.max(0, Math.min(index, steps.length - 1));
  document.querySelectorAll("[data-panel]").forEach((panel) => panel.hidden = panel.dataset.panel !== steps[state.step]);
  document.querySelectorAll(".step").forEach((step, idx) => step.classList.toggle("active", idx === state.step));
  qs("backBtn").disabled = state.step === 0;
  qs("nextBtn").textContent = state.step === steps.length - 1 ? "Create plan" : "Continue";
  renderReview();
}
function addCharacter() {
  const name = qs("characterName").value.trim();
  if (!name) return;
  state.characters.push({ name, description: qs("characterDescription").value.trim(), voice_traits: qs("characterVoice").value.split(",").map((x) => x.trim()).filter(Boolean) });
  ["characterName","characterDescription","characterVoice"].forEach((id) => qs(id).value = "");
  renderCharacters();
}
function renderCharacters() {
  qs("characterList").innerHTML = state.characters.map((c, i) => `<div class="item"><strong>${c.name}</strong><p>${c.description}</p><button class="secondary" onclick="removeCharacter(${i})">Remove</button></div>`).join("");
}
function removeCharacter(index) { state.characters.splice(index, 1); renderCharacters(); }
function addScene() {
  state.scenes.push({ act: Number(qs("sceneAct").value), scene: Number(qs("sceneNumber").value), setting: qs("sceneSetting").value.trim(), summary: qs("sceneSummary").value.trim(), participants: qs("sceneParticipants").value.split(",").map((x) => x.trim()).filter(Boolean) });
  ["sceneSetting","sceneSummary","sceneParticipants"].forEach((id) => qs(id).value = "");
  renderScenes();
}
function renderScenes() {
  qs("sceneList").innerHTML = state.scenes.map((s, i) => `<div class="item"><strong>Act ${s.act}, Scene ${s.scene}</strong><p>${s.setting}</p><p>${s.summary}</p><button class="secondary" onclick="removeScene(${i})">Remove</button></div>`).join("");
}
function removeScene(index) { state.scenes.splice(index, 1); renderScenes(); }
function renderReview() {
  const payload = collectPayload();
  const review = qs("reviewPayload");
  if (review) review.textContent = JSON.stringify(payload.user_input, null, 2);
}
function collectPayload() {
  return { request_id: requestId("plan"), user_input: { title: qs("title").value.trim(), overview: qs("overview").value.trim(), characters: state.characters, scenes: state.scenes } };
}
async function createPlan() {
  setStatus("Summoning the Expander...");
  const response = await fetch("/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectPayload()) });
  if (!response.ok) throw new Error(await response.text());
  state.plan = await response.json();
  qs("brief").textContent = state.plan.brief.markdown;
  setStatus(`Plan ${state.plan.plan_id} is ready. Review the brief, then approve it.`);
}
async function approveAndGenerate() {
  if (!state.plan) return;
  setStatus("Approving plan and composing a short cento draft...");
  await fetch(`/plan/${state.plan.plan_id}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId("approve"), approve: true, regenerate: false }) });
  const config = await (await fetch("/admin/config")).json();
  const response = await fetch("/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId("generate"), plan_id: state.plan.plan_id, config }) });
  if (!response.ok) throw new Error(await response.text());
  const result = await response.json();
  window.location.href = `/composer?job=${encodeURIComponent(result.job_id)}`;
}
function wireSetup() {
  qs("addCharacter").onclick = addCharacter; qs("addScene").onclick = addScene;
  qs("backBtn").onclick = () => showStep(state.step - 1);
  qs("nextBtn").onclick = async () => { try { state.step === steps.length - 1 ? await createPlan() : showStep(state.step + 1); } catch (error) { setStatus(error.message); } };
  qs("generateBtn").onclick = async () => { try { await approveAndGenerate(); } catch (error) { setStatus(error.message); } };
  showStep(0);
}
if (document.body.dataset.page === "setup") wireSetup();
