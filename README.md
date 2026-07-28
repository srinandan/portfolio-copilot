# Portfolio Copilot

Portfolio Copilot is a personal finance and investing assistant that
plans its own next move.

Instead of following a fixed script, a single agent looks at your goal,
checks what it's currently allowed to do, and decides for itself how to
get there — pulling in research, checking your portfolio, drafting a
trade if one's warranted. Nothing happens with your money without your
sign-off, and every decision it makes is traceable back to exactly which
capability made it, and why.

## Why try it

- **It plans, it doesn't run a script.** Ask it something and watch it
  work out, in the moment, what it needs to check and do — not a
  hardcoded pipeline of steps that runs the same way every time.
- **You can revoke what it's allowed to do, live, mid-conversation** —
  and watch it adapt on the very next step. No restart, no error.
- **Nothing happens with your money without you approving it first.**
  Proposed trades are drafted, checked against your own stated
  investment policy, and only ever executed after you say yes.
- **It's a real demonstration of agent governance**, not a slide about
  it — every action is traceable to the exact skill, version, and
  approval that authorized it.

This is a personal project and demo, built on Google Cloud's Gemini
Enterprise Agent Platform — not a product, not investment advice, and not
connected to a real brokerage (trades run through Alpaca's paper trading
API).

## Get started

Setup instructions live in [`install/`](install/). *(Coming soon — the
install path will be filled in once the agent itself is built.)*

## Learn more

How it's built, and the reasoning behind the key decisions: see
[`docs/spec/`](docs/spec/) and [`docs/adr/`](docs/adr/).
Contributor / coding-agent instructions: see [`AGENTS.md`](AGENTS.md).

## Status

Architecture and functional spec drafted. Implementation not yet started.

## Built With

This application was built with the assistance of [Stitch](https://stitch.withgoogle.com/) and [Jules](https://jules.google.com).

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details on how to contribute to this project.

## Support

This demo is *NOT* endorsed by Google or Google Cloud. The repo is intended for educational/hobbyists use only.

## License

This project is licensed under the terms of the [LICENSE](./LICENSE) file.
