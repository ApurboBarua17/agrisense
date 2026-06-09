# USDA Extension documents

Drop USDA extension PDFs (or .txt / .md files) here. On startup, the foundry-iq
service uploads them to an Azure AI Foundry vector store and creates a
file-search-enabled agent so treatment responses are grounded with citations.

## Where to get them

- https://extension.umn.edu/plant-diseases/tomato-diseases — download PDFs
- Focus on: early blight, late blight, bacterial spot, leaf mold
- 3-5 PDFs is enough for the demo

## Note

PDFs in this directory are excluded by .gitignore (large binaries). The
service tolerates the directory being empty — without docs, the agent falls
back to the LLM's built-in knowledge. Without `AZURE_AI_PROJECT_CONNECTION_STRING`,
the entire service falls back to a deterministic stub response so the demo
keeps working.
