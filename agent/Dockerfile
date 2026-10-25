FROM node:22-bookworm-slim

ENV HOME=/home/riri \
    FAILPROOFAI_HOME=/home/riri/.failproofai \
    PYTHONPATH=/opt/riri \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin \
    OPENCODE_DISABLE_AUTOUPDATE=1

ARG RIRI_UID=10001
ARG RIRI_GID=10001

RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-venv ca-certificates passwd \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --non-unique --gid "${RIRI_GID}" riri \
    && useradd --non-unique --uid "${RIRI_UID}" --gid "${RIRI_GID}" --create-home --shell /usr/sbin/nologin riri \
    && python3 -m venv /opt/venv

COPY agent/requirements.txt /opt/riri/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /opt/riri/requirements.txt

RUN npm install --global failproofai@1.0.12 opencode-ai@1.19.4

COPY agent/policy-selection.json agent/policies-config.json agent/opencode.json /opt/riri/
COPY agent/__init__.py agent/policy_gate.py agent/install_policy_pack.py agent/server.py agent/verify_policy_install.py /opt/riri/agent/
RUN mkdir -p /home/riri/.config/opencode /home/riri/.failproofai \
        /home/riri/.local/share/opencode /home/riri/.cache/opencode /data \
    && cp /opt/riri/opencode.json /home/riri/.config/opencode/opencode.json \
    && cp /opt/riri/policies-config.json /home/riri/.failproofai/policies-config.json \
    && chown -R riri:riri /home/riri /opt/riri /data

USER riri
WORKDIR /workspace

RUN failproofai policies --install block-sudo --cli opencode --scope user \
    && python -m agent.install_policy_pack \
    && python -m agent.verify_policy_install

EXPOSE 8081
CMD ["python", "-m", "agent.server"]
