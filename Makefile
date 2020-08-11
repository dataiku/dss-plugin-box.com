PLUGIN_VERSION=1.0.1
PLUGIN_ID=box-com

plugin:
	cat plugin.json|json_pp > /dev/null
	rm -rf dist
	mkdir dist
	zip --exclude "*.pyc" -r dist/dss-plugin-${PLUGIN_ID}-${PLUGIN_VERSION}.zip code-env parameter-sets python-fs-providers python-lib python-runnables plugin.json