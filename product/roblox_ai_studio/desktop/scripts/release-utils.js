'use strict';

function releaseChannel() {
  return (process.env.PLAYRO_RELEASE_CHANNEL || 'test').trim().toLowerCase();
}

function isProductionRelease() {
  return ['prod', 'production', 'stable'].includes(releaseChannel());
}

module.exports = {
  releaseChannel,
  isProductionRelease,
};
