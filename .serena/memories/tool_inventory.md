# Poetry MCP - Tool Inventory (17 Tools)

## Catalog Management
1. **sync_catalog** - Scan vault and build in-memory catalog index
2. **get_poem** - Retrieve poem by ID or title
3. **search_poems** - Search with filters (query, states, forms, tags)
4. **find_poems_by_tag** - Find poems by tag combinations
5. **list_poems_by_state** - List poems in specific states
6. **get_catalog_stats** - Get catalog statistics and health metrics
7. **get_server_info** - Server status and configuration

## Enrichment Tools
8. **get_all_nexuses** - Browse available themes, motifs, forms
9. **link_poem_to_nexus** - Add nexus tags to poem frontmatter
10. **sync_nexus_tags** - Sync [[Nexus]] wikilinks with frontmatter tags
11. **move_poem_to_state** - Move poems between state directories

## Agent Analysis Tools
12. **find_nexuses_for_poem** - Get poem + themes for agent to analyze and suggest matches
13. **get_poems_for_enrichment** - Get batch of poems for agent to analyze and suggest themes
14. **grade_poem_quality** - Get poem + quality rubric for agent to grade

## Quality Scoring Tools
15. **commit_quality_scores** - Write quality scores to poem frontmatter with validation
16. **get_quality_scores** - Retrieve existing quality scores from a poem
17. **find_high_scoring_poems** - Query poems by quality dimension and minimum score
18. **list_quality_dimensions** - Get available quality dimensions and descriptions

## Submission Tracking Tools
19. **get_venue** - Retrieve venue details by name
20. **list_venues** - Browse all tracked venues with filters
21. **get_submission_history** - View submission history for a poem or venue
22. **plan_submission** - Create planned submission record

Note: README states 17 tools, but 22 tools are listed when counting all categories. Need verification.
