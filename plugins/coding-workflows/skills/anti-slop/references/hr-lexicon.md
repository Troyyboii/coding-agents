# Hrvatski anti-klišej leksikon

Use when the target text is Croatian. Companion to the English patterns in `patterns.md`. Sources used to build this list: Croatian style tradition (Silić, Pravopis IHJJ, jezični savjeti) plus recurring failure modes of LLM-written Croatian.

## 1. Kalupi s engleskoga AI-slopa (English slop calqued into Croatian)

- "u današnjem brzom svijetu" / "u današnje vrijeme" / "u moderno doba" — delete, start at the thesis.
- "igra ključnu ulogu" / "odigrava važnu ulogu" — say what it concretely does.
- "važno je napomenuti" / "važno je istaknuti" / "treba naglasiti" — if it were important, it would not need announcing.
- "ne može se zanijekati" / "bez dvojbe" / "nesumnjivo" — evidence instead of claims about evidence.
- "nije samo X, nego i Y" — calque of "not just X but Y"; one half is usually ballast.
- "na kraju dana" / "sve u svemu" / "zaključno" — replace with an actual conclusion.
- "bogato tkivo" / "mozaik" / "šarenilo" / "pejsaž" (figurative) — tapestry/landscape/mosaic calques; ban in all metaphorical description.
- "putovanje" for anything that is not a journey — the "journey" calque.
- "otkriti" for describing texts ("članak otkriva") — "pokazuje", "dokazuje", or nothing.
- "sveobuhvatan" (comprehensive) — wrote the headline, not the text.
- "ključan" / "presudan" / "neophodan" — triple inflation; allow one per document, not per paragraph.
- "revolucionaran" / "transformativan" / "promjena paradigme" — sound without a number or date.
- "u današnjoj digitalnoj eri" — twice the slop in one phrase.
- Triple adjective stacks: "jedinstven, autentičan i nezaboravan" — Croatian LLMs love triads; one per text maximum.
- "duboko uroniti" / "uroniti u temu" — "deep dive" calque.
- "koristiti prednosti" / "iskoristiti mogućnosti" — "leverage/harness" calque; state the action.
- "postati imperativ" — "it is imperative" calque.
- "dinamičan" / "robusan" / "skalabilan" — three words that say nothing without a figure.
- "u kontekstu" / "u sklopu" / "na razini" — office-glue connectives; usually delete the whole phrase.
- "velik broj" / "brojni" / "mnoštvo" — give the number or an example.

## 2. Domaća kancelarija (native officialese — predates AI, AI breeds it)

- "vršiti" (vršiti provjeru → provjeriti), "provoditi" (provoditi analizu → analizirati), "realizirati" (realizirati plan → napraviti plan), "implementirati" where a native verb exists ("uvesti", "ugraditi").
- "u cilju" + noun → a verb with a purpose: "u cilju poboljšanja" → "da poboljša".
- "s obzirom na to da" / "imajući u vidu" / "uzimajući u obzir" → "jer" or "pošto".
- "u skladu s navedenim" — empty transition; delete.
- "navedeni" / "spomenuti" / "predmetni" (predmetni dokument) — replace with the name or "taj".
- "aktivnost" / "proces" / "mehanizam" / "aspekt" / "dimenzija" / "komponenta" / "parametar" — office abstracts; replace with a noun that does something.
- "u velikoj mjeri" / "u određenoj mjeri" / "u principu" — measure without a measure; delete or quantify.
- "izvršiti uplatu" → platiti. "doći do izražaja" → pokazati se. "nalaziti se" → biti.
- "po pitanju" — media tic; "o", "za", "oko".
- "evidentirati" / "registrirati" for plain "zabilježiti/primijetiti".
- "generalno" / "u globalu" / "paralelno" (meaning "usput") — false anglicisms.

## 3. Strukturalni govori (structural tells)

- Triads: "brzo, jednostavno i pouzdano" — one triad per text, not per section.
- Symmetric balance: every paragraph the same length, same thesis-example-summary shape. Break the rhythm deliberately.
- "Ne X, već Y" as a routine punch — strong move; own it in one text, not every text.
- Two-part headlines ("X: Y") everywhere.
- A conclusion that restates the introduction in new words — add the final thought or drop it.
- Passive without a subject ("preporučuje se", "smatra se") — who? Always who.
- Fake objectivity: "mnogi smatraju", "stručnjaci tvrde" — name the source or delete.
- Every non-taste claim: number, date, or name.

## 4. Gramatičke zamke (where LLMs actually break Croatian)

Word lists cannot catch these. Check before publishing:

1. **Agreement in gender:** "direktorica je došla", never "došao"; LLMs keep defaulting professions to masculine.
2. **je-li / li je:** "je li došao", not "li je došao"; "nije li", not "li nije".
3. **Noun + number:** 2–4 → genitive singular ("tri sata", not "tri sati"), 5+ → genitive plural ("pet sati"), 1 → singular. "dvije tisuće", not "dva tisuće".
4. **Prepositions and cases:** u/na + locative for position ("u Hrvatskoj"), u/na + accusative for direction ("u Hrvatsku"); s/z by sound cluster; "smatrati + instrumental" ("smatra ga prijateljem").
5. **Vocative:** normative -o → -e ("Marke", "Vlade"), -a → -o/-e ("Ano", "Vesno"); nominative address ("Marko!") is accepted in speech — the error is a nominative in formal writing where a vocative is expected. Instrumental is a separate case ("s Markom", "s Anom") — do not confuse it with the vocative.
6. **Verb valency calqued from English:** "baviti se čim", "sudjelovati u čemu", "radovati se čemu" (not "za nešto"), "sličiti na koga" — LLMs swap prepositions on the English model.
7. **Clitic second position:** "dao mi ga je", never "dao je mi ga"; clitics follow the first stressed word in subordinate clauses.
8. **biti word order:** "bio sam" when the verb carries stress, not "sam bio".
9. **Orthographic tics:** "što ga se tiče" (genitive), hyphens in compounds ("hrvatsko-engleski"), quotation marks for transferred meanings.

Deterministic first pass: LanguageTool with the `hr` language (self-hosted `languagetool/languagetool` Docker image or languagetool.org) — rule-based, catches spelling, punctuation and part of agreement. Do not trust AI grammar checkers without a rule base: they correct correct Croatian into English word order. HJP (hjp.znanje.hr) and pravopis.hr referee disputes.

## 5. Živi izvori za obogaćivanje (use while editing)

- **HJP — Hrvatski jezični portal** (hjp.znanje.hr): definitions, usage, attestation. First stop when an LLM offers a non-word.
- **Fran / Rječnik hrvatskoga jezika** (rjecnik.hr): broader senses and phrases.
- **Pravopis IHJJ** (pravopis.hr): free online orthography with notes and advice.
- **Baza frazema hrvatskoga jezika** (frazemi.ihjj.hr): authentic idioms instead of calques.
- **Jezični savjeti IHJJ** (ihjj.hr): answers to usage doubts.
- **Klaić** (loanwords) and **Šarić–Wittchen** (synonyms) for lexical variety when the model repeats one word.
- Dialect and vernacular as seasoning, only where a human writer would actually use it — never as simulated authenticity.

## 6. Mini-procedure

1. Search the text across sections 1–3; every hit: delete or replace with a concrete thought.
2. Break triads and symmetry by hand.
3. Every non-taste claim: number, date, or name.
4. Read aloud: where it stalls = officialese; where it sounds like an advert = an English calque. Both out.
5. Run section 4 checks before publishing.

English companion resources (not shipped here, fetch if needed): the Anti-Slop Writing Guide (github.com/louisfb01/ai-engineering-cheatsheets), tropes.fyi (gist by ossa-ma), the slopdetector.org AI words list, jodiecook.com/ban-list.
