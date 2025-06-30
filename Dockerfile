# SatNOGS auto-scheduler image
#
# Copyright (C) 2022 Libre Space Foundation <https://libre.space/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Build wheels for satnogs-auto-scheduler and ephem
FROM python:3.11-slim AS builder

# Install deps:
# - git: for hatch-vcs
# - build-essential: for ephem, on platforms where no matching wheel is available via PyPI
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get --no-install-recommends install -y git && \
    if [ "$(dpkg --print-architecture)" = "armhf" ]; then \
        apt-get --no-install-recommends install -y build-essential; \
    fi

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install build hatchling hatch-vcs

WORKDIR /build
COPY . .

# Build wheel for satnogs-auto-scheduler
RUN --mount=type=bind,source=.git,target=.git \
    rm -rf /dist/satnogs_auto_scheduler*.whl && \
    python3 -m build --no-isolation --wheel --outdir /dist/

# Build wheel for ephem
RUN --mount=type=cache,target=/root/.cache/pip \
    rm -rf /dist/ephem*.whl && \
    pip wheel --wheel-dir /dist/ ephem~=4.2

FROM python:3.11-slim
LABEL org.opencontainers.image.authors='sa2kng <knegge@gmail.com>'

ARG SATNOGS_CLIENT_UID=999
ARG SATNOGS_CLIENT_NAME=satnogs-client
ARG SATNOGS_CLIENT_VARSTATEDIR=/var/lib/satnogs-client


# Add unprivileged system user
RUN groupadd -r -g ${SATNOGS_CLIENT_UID} ${SATNOGS_CLIENT_NAME} \
	&& useradd -r -u ${SATNOGS_CLIENT_UID} \
		-g ${SATNOGS_CLIENT_NAME} \
		-d ${SATNOGS_CLIENT_VARSTATEDIR} \
		-s /usr/bin/false \
		-G audio,dialout,plugdev \
		${SATNOGS_CLIENT_NAME}

# Create application varstate directory
RUN install -d -o ${SATNOGS_CLIENT_UID} -g ${SATNOGS_CLIENT_UID} ${SATNOGS_CLIENT_VARSTATEDIR}

COPY --from=builder /dist/*.whl /dist/
RUN --mount=type=cache,target=/root/.cache/pip \
    PYTHONDONTWRITEBYTECODE=1 \
    pip install /dist/ephem*.whl /dist/satnogs_auto_scheduler*.whl

USER ${SATNOGS_CLIENT_NAME}
WORKDIR ${SATNOGS_CLIENT_VARSTATEDIR}
CMD ["bash"]
