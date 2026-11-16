# Content pipeline: requirements

Plan tasks: 2.1 to 2.4 (and 1.3 for the shared validator). Steering: product, tech, structure, license-record.

## Introduction
A repeatable script builds the Mesurado content pack from openly licensed sources: select, clean, index, package,
validate. The pack is built once while online, then copied to Android phones and laptops. Every item and every
passage must trace to a source and a license, so Ask mode can cite and the project can be redistributed lawfully.

Glossary
- **Item**: an article, image or other asset in the pack.
- **Passage**: a chunk of an article (about 150 to 300 words) with a heading path; the unit that search and Ask cite.
- **Manifest**: the file listing every item with source, license, revision and attribution.
- **Pack**: ZIM file of articles and media, plus the indexes, the passage store and the manifest.
- **Validator**: the shared checker used by the build and by the pack-validator MCP server.

## Requirements

### R1. Source selection
**User story:** As the builder, I want one reviewed list of sources so that the pack contains only what I chose and can defend.
1. WHEN the pipeline starts, THE pipeline SHALL read a selection file (`pipeline/selection.yaml`) listing topics and source identifiers, grouped by subject.
2. THE selection file SHALL group items into subjects so that pack v1 can be built from history and geography only, and science and mathematics added later without code changes.
3. IF a selected source is not from an allowed source (Wikipedia, Wikimedia Commons, OpenStax, or another source with an explicit open license listed in the file), THEN THE pipeline SHALL stop with an error naming the source.

### R2. Manifest and license record
**User story:** As a judge or redistributor, I want every item's source and license recorded so that the pack is clearly lawful to share.
1. WHEN an item is fetched, THE pipeline SHALL record in the manifest: id, title, source URL, revision, SPDX license id, attribution text, retrieval date and modifications.
2. THE pipeline SHALL pin Wikipedia articles to a revision id so that rebuilds fetch the same text.
3. WHEN an image is fetched, THE pipeline SHALL read its license from Commons file metadata and SHALL exclude the image when the license is missing or not on the allowed list.
4. THE manifest SHALL be human-readable and committed to the repo even when the large pack files are not.

### R3. Cleaning and passages
**User story:** As a student, I want clear readable text and precise sources so that answers point at the right place.
1. WHEN an article is fetched, THE pipeline SHALL remove navigation, edit links, reference markers, empty sections and templates that do not render useful text.
2. THE pipeline SHALL split each article into passages of about 150 to 300 words on paragraph boundaries, and SHALL keep the heading path (for example "History > Colonization") for each passage.
3. THE pipeline SHALL give each passage a stable id derived from its article id and position, so ids stay the same when the article text is unchanged.
4. THE pipeline SHALL store each passage's article id and character offsets so that the app can scroll to and highlight the passage in the article.
5. IF an article yields no passage after cleaning, THEN THE pipeline SHALL report it and drop it from the pack.

### R4. Index and embeddings
**User story:** As a student on a cheap phone, I want fast search so that results appear in about a second.
1. THE pipeline SHALL build a keyword index over passages and article titles.
2. THE pipeline SHALL compute one compact embedding per passage with a pinned open-license model, quantized to 8 bits, and SHALL record the model name, version and license in the pack metadata.
3. THE indexes SHALL load on the demo Android phone within the size and time budgets in design.md.
4. THE pipeline SHALL be deterministic: the same selection, revisions and configuration SHALL produce the same index and embeddings.

### R5. Packaging
**User story:** As the builder, I want a single pack I can copy to a phone so that no network is needed.
1. THE pipeline SHALL write articles and images to a ZIM file, and the passage store, indexes, metadata and manifest to files in the same pack directory.
2. THE pipeline SHALL downscale and compress images so that the total pack stays within the size budget in design.md.
3. THE pipeline SHALL write a pack version and a content hash into the pack metadata.
4. THE pipeline SHALL build into a new directory and SHALL NOT leave a partial pack in place if any stage fails.

### R6. Validation
**User story:** As the builder, I want the build to fail when anything is unlicensed or untraceable so that I cannot ship a mistake.
1. WHEN the pack is packaged, THE validator SHALL fail the build if any item lacks a source URL, a revision, an allowed license or attribution text.
2. THE validator SHALL fail the build if any passage cannot be traced to its article, or its offsets do not match the article text.
3. THE validator SHALL fail the build if the pack contains a file that has no manifest entry, or the manifest lists a file that is missing.
4. THE validator SHALL fail the build if any text or file in the pack contains the word "Encarta".
5. THE validator SHALL print a report with counts of items, passages, licenses and failures, and SHALL exit non-zero on any failure.
6. THE same validator code SHALL be callable by the build, by tests and by the pack-validator MCP server.

### R7. Attribution output
**User story:** As a reader, I want to see where content came from so that I can trust it and credit it.
1. THE pipeline SHALL generate an attribution file listing each item's title, author or source, license and link.
2. THE pipeline SHALL generate per-article credit text for the app to display on every article page.

### R8. Reproducibility and speed
1. THE pipeline SHALL cache fetched source files locally so that a rebuild does not need the network when nothing changed.
2. THE pipeline SHALL run from one command and SHALL print the stage it is in and a summary at the end.
3. WHEN only the selection of one subject changes, THE pipeline SHALL reuse cached cleaning and embedding results for unchanged articles.

### R9. Sample questions and quiz seeds
**User story:** As a student, I want example questions to start from so that I know what the pack can answer.
1. THE pipeline SHALL write `sample-questions.json`: for each subject, at least 10 example questions, each linked to the passage id that answers it.
2. THE pipeline SHALL create the sample questions by a rule-based method from passage headings and first sentences, or from a reviewed hand-written list, and SHALL NOT use a generative model at build time unless its output is reviewed and recorded.
3. THE validator SHALL fail the build if a sample question links to a passage id that does not exist.
4. THE same file MAY seed quiz questions; the quizzes spec defines how quizzes use it.

## Out of scope
Live updates, user-contributed content, any source that is not openly licensed, generating articles with a model.
