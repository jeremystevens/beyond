# Break down larger requests

First version: `/steps <request>` explicitly opts into a bounded planning-and-drafting workflow. No additional composer controls. Plan one to three parts, draft each with prior parts as context, then stream one cohesive final answer. Show progress through the existing chat status and reuse Stop cancellation. Ordinary chat and Think it through remain unchanged.

At most five model calls, including planning and synthesis; at most six minutes total. Context and intermediate drafts are bounded. The mode drafts content only: it does not execute code, create files, or independently verify facts. Malformed model plans use a clearly announced standard drafting plan; JSON, numbered and bulleted plans are accepted. Empty drafting output fails visibly. Existing lookup and permission handling still applies before drafting.

Known first-version limitation: Retry uses the ordinary reply path; invoke /steps again to repeat the multi-part workflow. CPU processing can be slow. Real-model testing and documentation review are required before merging. Release VERSION remains unchanged until the release workflow is followed.
