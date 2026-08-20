# Repaso

A reinforcement tutor that families run from Telegram. The parent feeds it whatever
material the school sends — notebook photos, PDFs, weekly plans. The agent turns it
into a daily adaptive micro-practice loop for each student, regulated by measured
performance, and interrupts a human only when there is a real decision to make.

Built for the **AWS Agents for Humans Hackathon** on the Strands Agents SDK and
Amazon Bedrock AgentCore. The full README — agent fleet, guarantees, architecture
diagram, benchmark reports, and pilot results — lands with the submission.

## Quick start (no AWS account required)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The offline suite and the demo clock run entirely in local mode: every AWS
dependency sits behind a protocol with an on-disk implementation, and no network
access or credentials are needed.

## License

MIT
