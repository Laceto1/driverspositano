export const meta = {
  name: 'swarm-research',
  description: 'Swarm research on any question: expert source map, one agent per track, adversarial fact-check per track, completeness critic, gap fill, merge in code, section writers',
  whenToUse: 'Any research, list-building, "find the best X" or "how do I fix X" question that needs exhaustive, fact-checked coverage. Args: {question, today, maxTracks?, maxGaps?, sources?}',
  phases: [
    { title: 'Map', detail: 'expert maps every source and research track' },
    { title: 'Research', detail: 'one agent per track' },
    { title: 'Verify', detail: 'one skeptic per track, primary sources' },
    { title: 'Critique', detail: 'completeness critic finds gaps' },
    { title: 'Fill gaps', detail: 'one agent per gap, then fact-check' },
    { title: 'Write', detail: 'section writers, assembled in code' },
  ],
}

// Usage: Workflow({name: 'swarm-research', args: {question: '...', today: 'YYYY-MM-DD', maxTracks: 24, maxGaps: 6, sources: 'optional extra source hints'}})
// Lessons built in: never slice merged material to fit one writer (merge in code, chunk writers);
// fact-checkers open primary sources with WebFetch and use few searches (shared budget);
// PubMed web pages show a bot check, so use E-utilities / Europe PMC; agents never write files.
const Q = args && args.question
if (!Q) throw new Error('swarm-research needs args.question')
const TODAY = args.today || 'today'
const MAX_TRACKS = args.maxTracks || 24
const MAX_GAPS = args.maxGaps === undefined ? 6 : args.maxGaps

const NOTE = `Today is ${TODAY}. Load WebSearch/WebFetch with ToolSearch ("select:WebSearch,WebFetch") if needed. Prefer primary sources (official registries and directories, regulators, guidelines, systematic reviews, filings, original papers) over listicles and ads. Rank evidence: guidelines/systematic reviews > trials > smaller studies > opinion, and say which level each claim rests on. Literature: PubMed web pages show a bot check, so use https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term=<q> / esummary.fcgi / efetch.fcgi, or https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query=<q>. The network only allows some hosts. WebFetch can fail with ENOTFOUND on hosts the environment does allow: when it does, fetch the same URL once with Bash instead: curl -sSL -m 30 -A 'Mozilla/5.0' '<url>' | head -c 30000 (print to stdout; never save files into the repo). If both fail, do not retry. Use WebSearch at most 6 times (shared budget). Do NOT write any files. Never invent names, numbers, dates or URLs: every item needs a source URL you actually saw.${args.sources ? '\nExtra sources: ' + args.sources : ''}`

const ITEMS = {
  type: 'object',
  properties: {
    items: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, category: { type: 'string', description: 'short section name, e.g. "Doctors", "Treatments", "Causes"' },
      details: { type: 'string' }, status: { type: 'string', description: 'approval/regulatory/credential status with date, if relevant' },
      evidence: { type: 'string', description: 'evidence level, study type/size/year, or credential proof' },
      sources: { type: 'array', items: { type: 'string' } },
    }, required: ['name', 'category', 'details', 'sources'] } },
    notes: { type: 'string' },
  },
  required: ['items'],
}
const CHECKS = {
  type: 'object',
  properties: { checks: { type: 'array', items: { type: 'object', properties: {
    item: { type: 'string' }, verdict: { type: 'string', enum: ['verified', 'corrected', 'refuted', 'unverifiable'] },
    correction: { type: 'string' }, source: { type: 'string' } }, required: ['item', 'verdict'] } } },
  required: ['checks'],
}

phase('Map')
const map = await agent(`You are the world's leading expert on this question: "${Q}". ${NOTE}
Do NOT research yet. Split the research into up to ${MAX_TRACKS} independent tracks that together leave no stone unturned, including non-obvious sources a layperson would never think of (registries, regulators, guidelines, trial registries, professional societies, filings, regional angles, specific patient/user groups, recent developments, and what is hype). Each track: short id, precise focus, named sources/queries to use.`,
  { phase: 'Map', schema: { type: 'object', properties: { tracks: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, focus: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } } }, required: ['id', 'focus'] } } }, required: ['tracks'] } })
let tracks = (map && map.tracks) || []
if (tracks.length > MAX_TRACKS) { log(`Dropped tracks beyond ${MAX_TRACKS}: ${tracks.slice(MAX_TRACKS).map(t => t.id).join(', ')}`); tracks = tracks.slice(0, MAX_TRACKS) }
log(`${tracks.length} tracks mapped`)

const research = (focus, label, phaseName) => agent(`Overall question: "${Q}".
Research this track: ${focus}
${NOTE}
Return the strongest items (up to 15) with category, details, status, evidence and sources. Caveats go in notes.`, { phase: phaseName, label, schema: ITEMS })

const verify = (found, label) => agent(`You are a skeptical fact-checker. Try to REFUTE these findings for the question "${Q}". ${NOTE}
Open the primary source for each key claim (names, credentials, approval status and dates, numbers, study sizes, quotes). Verdict per item: verified / corrected (give the correction) / refuted / unverifiable. Put the item's exact name in "item" and the confirming or refuting URL in "source". Default to unverifiable if you cannot confirm.
FINDINGS:
${JSON.stringify(found).slice(0, 20000)}`, { phase: 'Verify', label: `verify:${label}`, schema: CHECKS })

const done = (await pipeline(tracks,
  t => research(`${t.focus}${t.sources ? ' | Sources: ' + t.sources.join('; ') : ''}`, `research:${t.id}`, 'Research'),
  (found, t) => found && verify(found, t.id).then(v => ({ id: t.id, found, v })),
)).filter(Boolean)
log(`${done.length}/${tracks.length} tracks researched and fact-checked`)

phase('Critique')
let gapDone = [], gaps = []
if (MAX_GAPS > 0) {
  const covered = done.map(d => `${d.id}: ${(d.found.items || []).map(i => i.name).join(', ')}`).join('\n')
  const crit = await agent(`You are a completeness critic for research on "${Q}" (today ${TODAY}). List up to ${MAX_GAPS} important gaps: sources not used, groups/regions missing, items or recent developments missing, claims needing a primary source. Each gap must be a concrete research task.
COVERED:
${covered}`, { phase: 'Critique', schema: { type: 'object', properties: { gaps: { type: 'array', items: { type: 'string' } } }, required: ['gaps'] } })
  gaps = ((crit && crit.gaps) || []).slice(0, MAX_GAPS)
  log(`Critic found ${gaps.length} gaps`)
  gapDone = (await pipeline(gaps,
    (g, _g, i) => research(g, `gap:${i + 1}`, 'Fill gaps'),
    (found, g, i) => found && verify(found, `gap-${i + 1}`).then(v => ({ id: `gap-${i + 1}`, found, v })),
  )).filter(Boolean)
}

// Merge in plain code: attach verdicts, drop refuted, dedupe. No truncation.
phase('Write')
const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim()
const clip = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n) + '…' : s }
const verdictFor = (name, checks) => { const n = norm(name)
  return (checks || []).find(c => { const ci = norm(c.item); return ci && n && (ci.includes(n) || n.includes(ci)) }) || { verdict: 'unverifiable' } }
const counts = { verified: 0, corrected: 0, unverifiable: 0, refuted: 0 }
const merged = new Map(), notes = []
for (const d of [...done, ...gapDone]) {
  if (d.found.notes) notes.push(clip(d.found.notes, 500))
  for (const x of d.found.items || []) {
    const v = verdictFor(x.name, d.v && d.v.checks); counts[v.verdict]++
    if (v.verdict === 'refuted') continue
    const k = norm(x.name), prev = merged.get(k)
    const item = { name: x.name, category: clip(x.category || 'Other', 40), details: clip(x.details, 400), status: clip(x.status, 200),
      evidence: clip(x.evidence, 300), sources: (x.sources || []).slice(0, 3), check: v.verdict, correction: clip(v.correction, 240), check_source: v.source || '' }
    if (!prev) merged.set(k, item)
    else if (prev.check === 'unverifiable' && v.verdict !== 'unverifiable') Object.assign(prev, { check: v.verdict, correction: item.correction, check_source: item.check_source })
  }
}
const all = [...merged.values()]
log(`Merged ${all.length} items; checks ${JSON.stringify(counts)}`)

const RULES = `Today is ${TODAY}. Use ONLY the material given; never add facts. Items have check = verified | corrected | unverifiable: apply corrections; mark unverifiable items "(unconfirmed)". Cite sources as markdown links.`
// Group categories so small ones don't each get a writer: keep the 7 biggest with 4+ items, fold the rest into "Other findings".
const catSize = {}
for (const it of all) catSize[it.category] = (catSize[it.category] || 0) + 1
const keep = new Set(Object.entries(catSize).filter(([, n]) => n >= 4).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([c]) => c))
const byCat = {}
for (const it of all) { const c = keep.has(it.category) ? it.category : 'Other findings'; (byCat[c] = byCat[c] || []).push(c === it.category ? it : { ...it, details: `[${it.category}] ${it.details}` }) }
const jobs = []
for (const [cat, items] of Object.entries(byCat)) {
  let cur = []
  const flush = part => { const c = cur; cur = []; jobs.push(agent(`${RULES}
Write markdown for section "### ${cat}${part ? ' (part ' + part + ')' : ''}": a table name | details | status | evidence | check | sources, keeping every item, verified/corrected first, then 1-3 sentences on what stands out.
MATERIAL:
${JSON.stringify(c)}`, { phase: 'Write', label: `write:${cat}${part ? '-' + part : ''}` })) }
  let part = 0
  for (const it of items) { cur.push(it); if (JSON.stringify(cur).length > 40000) flush(++part) }
  if (cur.length) flush(part ? ++part : 0)
}
const sections = await Promise.all(jobs)
const compact = all.map(i => `${i.category} | ${i.name} | ${clip(i.status || i.details, 160)} | ${i.check}`).join('\n')
const bottom = await agent(`${RULES}
Answer the question "${Q}" in "## Bottom line": 6-10 bullets with the key answers, what to do first, caveats, and what still needs checking. Then "## Caveats" from these researcher notes. Base it only on the item list and notes.
ITEMS:
${compact}
NOTES:
${JSON.stringify(notes)}`, { phase: 'Write', label: 'write:bottom-line' })

const report = `# ${Q}\n\n**Date:** ${TODAY}. Research summary from a fact-checked agent swarm.\n\n${bottom}\n\n## Findings\n\n${sections.join('\n\n')}\n\n## Coverage and limits\n\n- Tracks: ${done.length}/${tracks.length} (${done.map(d => d.id).join(', ')}).\n- Gaps filled: ${gapDone.length}/${gaps.length}${gaps.length ? ': ' + gaps.map(g => clip(g, 100)).join(' | ') : ''}.\n- Fact-checks: ${counts.verified} verified, ${counts.corrected} corrected, ${counts.unverifiable} unconfirmed, ${counts.refuted} refuted (dropped). ${all.length} items after de-duplication.\n`
return { report, stats: { tracks: tracks.length, done: done.length, gaps: gaps.length, gaps_done: gapDone.length, items: all.length, counts } }
