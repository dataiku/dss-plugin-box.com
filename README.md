# Box.com Plugin
This plugin provides a read connector to interact in your Dataiku DSS projects with csv documents stored on [box.com](https://www.box.com).

## Install in DSS
To install **Plugin: Box.com** in DSS, go to *Administration > Plugins > Store* and search for the plugin name.

Alternatively, [Download it]() (for DSS 6+) and follow our [installation instructions](https://doc.dataiku.com/dss/latest/plugins/installing.html)

## Plugin information

|   |   |
|---|---|
| Version  | 1.0.0 |
| Author  | Dataiku |
| Released  | 2019-09 |
| Last updated  | 2019-09 |
| License  | Apache Software License |
| Source code  | [Github](https://github.com/dataiku/dataiku-contrib/tree/master/googlesheets) |
| Reporting issues  | [Github](https://github.com/dataiku/dataiku-contrib/issues) |

## How to use

You need to install the plugin in Dataiku DSS. Go to the *Administration > Plugins* page. The plugin requires the installation of a code environment.

Create a new dataset using the plugin. You have 3 parameters to fill. Click on the button **Test** & **Get schema** button. Then, **save** and **explore**.

In order to use the plugin, the administrator of the box.com account will have to create an box.com app: 

1. As administrator, go to your [box.com account page](https://app.box.com/account) and upgrade to developper.
2. From the administrator's [developers console](https://app.box.com/developers/console), create a new Partner Integration.

![](images/select_app_type.png)

3. Name your app.
> People given access to this app will be able to access all files shared to it. Where access to dataset must be restricted to a given group, make and name a separate app for this purpose.
4. From the App configuration panel, create and copy a secondary access token.

![](images/app_config.png)

5. Go to the plugin's setting page and create a preset. In the preset, paste the access token. 

![](images/create_preset.png)

Once you have the access token, you will be able to retrieve the app's sharing email address. To do so:
1. Inside a DSS project, go to the **Macros** menu

![](images/macro_menu.png)

2. Select the **Get Box.com sharing email** macro

![](images/select_macro.png)

3. Pick a previously created preset, or fill in the access token using **Manually defined**. Then press **Run Macro**

4. Copy the email address returned.

![](images/sharing_email_address.png)

To make files visible to DSS, you will need to share them from your box account with this email address.

Once this is done, you can create a new dataset using the box.com plugin. First, create the dataset by picking box.com in the dataset section :

![](images/create_dataset.png)

Choose the Filesystem provider, and fill in the details copied from the app configuration panel.

![](images/plugin.png)

From the connector's *Settings > Files* panel, you should now be able to browser your box directory and select the file or directory you want to access.

![](images/browsing.png)

Browsing speed can be slightly increased by activating the cache option. However this is not available in MUS context. 

## Write mode

- Edit the `DATADIR/config/dip.properties` file and add the following key: `dku.datasets.external.no_connection.allowClear=true`
- Share an empty directory with the box.com dss app. It is important that it does not contain data you want to keep: **the entire structure contained inside this directory can be deleted by the plugin**.
- In the flow, first create your target box.com dataset, by selecting the box.com plugin in the dataset list.
- Browse to your target directory, name this new dataset and press **create**
- If the following message appears : `An invalid argument has been encountered : Missing parameters for CSV` got to the dataset *Settings > Format / Preview* and set *Quoting style*

![](images/set_quoting_style.png)

- Pick the source dataset and create a sync recipe from it. Select *Use existing dataset* and pick your target box.com dataset. Finally **Create recipe**.

![](images/create_sync.png)
