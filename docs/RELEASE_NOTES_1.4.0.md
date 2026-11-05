# BEYOND 1.4.0

## Chat and tool improvements

- Beyond calculates supported budget, time, capacity, pack-price, and checkout questions locally. Budget corrections use the latest amount in the chat.
- Explicit requests for JSON objects, exact bullet counts, and replies without an introduction take priority over default chat style. Beyond removes recognized wrappers when it can preserve the answer content.
- Automatic web and weather routing better distinguishes chat instructions and device-temperature questions from requests for current information.
- Recalled replies are labeled as unverified history. Requests to use only supplied facts bypass automatic lookup and unrelated recalled or learned context.
- Quoted references, attachments, and web snippets are separated from task instructions. Supported tank capacity, battery duration, and item weight questions can use values stated directly in an attachment or lookup result.
- Contributors can run the opt-in model smoke test for formatting, arithmetic, and routing.

## Known limitations

Models can still overlook missing or conflicting evidence. Instructions embedded in sources can still affect answers outside the supported extraction cases. See [issue #23](https://github.com/jeremystevens/beyond/issues/23) and [issue #25](https://github.com/jeremystevens/beyond/issues/25).

## Updating

Use **Settings ? Updates** or the included Update-Beyond.cmd launcher after the release is available. The updater preserves chats, settings, memories, models, and user files. Finish active work before updating. Python 3.14 (64-bit) is required.
