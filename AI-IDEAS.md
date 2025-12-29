# AI Ideas Tracker

**Last Updated:** 2025-12-24

## Legend
**Status:** 🟢 Built | 🟡 In Progress | 🔴 Planned | 🔵 Research | ⚪ Idea


---

## Ideas List

| Idea | Status | Type | Notes |
|------|--------|------|-------|
| Secret Savas - Slack RAG personality analyzer | 🟢 | Internal | 700K msgs, $0.50/user, blog ready, `savas-scripts/not/RAG-test-Slack/` |
| Website scraper / quality analyzer | 🟡 | Internal | Be exhaustive on all the things it could check: Spelling/SEO/WCAG/security, caught real bugs. Forbes misspelling on that page - https://www.linkedin.com/in/phoebe-c-liu/ https://www.forbes.com/sites/phoebeliu/2025/09/17/the-ai-billionaire-youve-never-heard-of/ - ai billionaires  Crawl4AI for research/content curation  Scraper: https://chatgpt.com/c/6920031a-3b08-8327-9326-4550cdb53cd0 I also just found that the taxonomy term for AI is not checked in the view – so it fails when you go to it 🤦  – this should be added to the screening tool – clicks everything and finds non-standard behavior. Maybe we ca provide some sort of service that an agent can update the site and document the fixes it’s made, and charge for that service as a monthly subscription or something I could imagine it having permission to log into the Drupal site, fixing the typo, documenting it, and  Things like typos maybe don’t recur a bunch, but people not adding  What about an agent that can login to a Drupal/WordPress site – it’s interesting 🤔 Maybe the agent does thee update on your staging site and runs some other tests and takes a screenshot so you can just quickly approve the update. Could also be triggered on any site change. |
| LLM-assisted content categorization | 🟡 | Internal | Auto-tag/categorize large content libraries - could do an update to Savas's shitty tagging, both looking for all our tags, suggesting reduction, anything with fewer than 3 -- anyhting that's a subset, going to higher category |
| Document quality analyzer | 🟡 | Internal | Pre-review proposals/kickoffs for Lu/Zakk Task Orders -- check against spelling, spacing, grammar, other quality metrics.  `proposal-submission-workflow/` -- did some work there |
| going from strategic proposal time to kickoff | ⚪  | Internal | should determine/reuse stuff from sales when moving to kickoff - not sure this is anything ai, maybe just part of document quality checkoff, and the proposal is the source. this should be part of document quality checker one|
| Meeting/idea scoring system | 🔵 | Internal | Score meetings/ideas against criteria (from Striver) |
| Weekly Slack update meeting order agent | 🟡  | Internal | **Needs fix**  Airtable + Slack MCP server + Google Calendar |
| Drupal/WordPress update agent | 🟡 | Internal | Auto-test staging, visual regression / HTML comparison (should be able to do for all pages easily enough), create PRs, verify form submissions (contact still works). Minor version test and then move to major version |
| Multi-source knowledge base (Savas unified search) | 🟡  | Internal | Slack + Drive + GitHub + Harvest + Teamwork + Fathom, single search interface - need to be thoughtful/clear about use cases but demoing searchability AND auto-triggers on things that matter that we might want to be alerted about -- connected to document quality checking automation |
| Auto-email unsubscriber | 🟡 | Internal | I'd like to give a tool access to my email, and go through and unsubscribe from all tools on messages that are marked as |
| Proposal/task order automation of creation, there are services, but how do we make custom design look good and be readily buildable | 🔵 | Internal | Template generation, `proposal-submission-workflow/` |
| Some sort of self-asssments demo | 🔴 | Internal | Kirsten's idea, maybe it couples with the scraper and you get some brief insights - Kirsten’s tool – maybe we can LLM-ify crawling someone’s site – looking for typos as an example, and also assessing if it’s LLM ready https://techcrunch.com/2025/11/18/hugging-face-ceo-says-were-in-an-llm-bubble-not-an-ai-bubble/  |
| Agents searching how to make site run leaner (DB queries) | 🔴 | Internal | Ways to automatically / programmatically check opportunities to reduce bloat so I don’t have to pay more for Drupal site on Platform.sh / Upsun Can it scour and see files, and look for things that are no longer referenced from the site, or bloaty-y ass tables|
| Prospect researcher bot | 🔴 | Internal | A bot that can scrape twitter, give sentiment, and recommend what that decision maker would like to hear in a proposal Could be broader scrape of all public internet – could be for sales too HubSpot and Salesforce must have really sophisticated tools for this, scraping all sorts of things about sentiment, personality, buying advice on individuals. I wonder 🤔 – maybe it’d be bad to be in that system though |
| speeding up case study generation | 🔴 | Internal | It would be nice to vibe that up fast, reducing the time it takes us, so we'd get them out more quickly |
| Client-specific SLM training / private fine-tuned models | 🔵 | Product | Research complete, POC ready. See `projects/small-private-model-research/RESEARCH.md`. Hybrid approach: fine-tune for style + RAG for knowledge. |
| Psychiatry | ⚪ | Internal | – who’s creating data for RL – video (sentiment), plus audio (sentiment), plus transcript |
| Quickbooks sucks,  | ⚪ | Internal | and that should be AI-able, and be like $10/month and allow me to just quickly scan and verify. No email with my person. Would be easy to view old transactions and how they’re cat |
| Set up fast way to image-gen with brand | ⚪ | Internal | I'd like to be able to create images based off of our brand, which is captured in Figma at : https://www.figma.com/design/2tGTNCpgtue8QF6BFASPFX/-SAVAS--Brand?node-id=2905-2535&p=f&t=YVH6X1bRNUCbjSMP-0  was trying to get top models to be able to compete and generate a few ideas around using ava as a personified AI thing https://chatgpt.com/c/694f1f40-fea0-832c-b209-f2d30fd4b934 STM Branding too: https://www.figma.com/design/QCLxZEYSwD6YNSmdj2f0hv/-STM--Branding?node-id=158-1247&p=f&t=R1PUCDVLwKy3oXnd-0 - almost created paid midjourney account, have gemini |
| Selecting tools based on their vibe-ability | ⚪ | Internal | if we think wordpress/drupal can't, then we pivot. Or we make them. But frameworks that don't work with codegen tools are not our future |







---

## Client-Specific (RIF)

| Idea | Status | Type | Notes |
|------|--------|------|-------|
| RIF semantic search - PDFs/videos/PowerPoints | 🟢 | Product | 21K resources vectorized, demo built |
| RIF AI-powered resource generation | 🔵 | Product | Generate word searches, crosswords at scale |
| RIF GEO/AEO optimization | 🔵 | Product | Answer engine optimization, Share of Voice tracking |
| RIF personalization + behavioral nudging | 🔵 | Product | CRM integration for conversion KPIs |
| RIF multilingual features | 🔵 | Product | Drupal native + machine translation |
| PDF → HTML conversion tool | 🔵 | Product | LLM-assisted validation |
| Video transcript extraction tool | 🔵 | Product | YouTube + Vimeo transcripts → searchable text |
| Personalization + CRM integration | 🔵 | Product | Behavioral nudging for conversion KPIs |
| Newsletter signup optimization | 🔵 | Product | Reduce friction, progressive profiling |
| Partnership/donor journey optimization | 🔵 | Product | Conversion optimization for nonprofits |
| Registered user feature enhancement | 🔵 | Product | Account features for content platforms |

---


