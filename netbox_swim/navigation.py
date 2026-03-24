from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu

menu = PluginMenu(
    label='OS & Firmware Upgrades',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:netbox_swim:dashboard',
                link_text='Dashboard',
                permissions=[],
            ),
        )),
        ('Image Repository', (
            PluginMenuItem(
                link='plugins:netbox_swim:softwareimage_list',
                link_text='Software Images',
                permissions=['netbox_swim.view_softwareimage'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:softwareimage_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_softwareimage']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:fileserver_list',
                link_text='File Servers',
                permissions=['netbox_swim.view_fileserver'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:fileserver_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_fileserver']),),
            ),
        )),
        ('Compliance & Workflows', (
            PluginMenuItem(
                link='plugins:netbox_swim:hardwaregroup_list',
                link_text='Hardware Groups',
                permissions=['netbox_swim.view_hardwaregroup'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:hardwaregroup_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_hardwaregroup']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:goldenimage_list',
                link_text='Golden Images',
                permissions=['netbox_swim.view_goldenimage'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:goldenimage_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_goldenimage']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:devicecompliance_list',
                link_text='Compliance Report',
                permissions=['netbox_swim.view_devicecompliance'],
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:workflowtemplate_list',
                link_text='Workflow Templates',
                permissions=['netbox_swim.view_workflowtemplate'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:workflowtemplate_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_workflowtemplate']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:checktemplate_list',
                link_text='Check Templates',
                permissions=['netbox_swim.view_checktemplate'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:checktemplate_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_checktemplate']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:validationcheck_list',
                link_text='Validation Checks',
                permissions=['netbox_swim.view_validationcheck'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:validationcheck_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_validationcheck']),),
            ),
        )),
        ('Execution Engine', (
            PluginMenuItem(
                link='plugins:netbox_swim:upgradejob_list',
                link_text='Upgrade Jobs',
                permissions=['netbox_swim.view_upgradejob'],
                buttons=(PluginMenuButton(link='plugins:netbox_swim:upgradejob_add', title='Add', icon_class='mdi mdi-plus-thick', permissions=['netbox_swim.add_upgradejob']),),
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:devicesyncrecord_list',
                link_text='Consolidated Sync Results',
                permissions=['netbox_swim.view_devicesyncrecord'],
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:syncjob_list',
                link_text='Sync Jobs Tracking',
                permissions=['netbox_swim.view_syncjob'],
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:device_bulk_sync',
                link_text='Bulk Device Sync',
                permissions=['netbox_swim.add_upgradejob'],
            ),
            PluginMenuItem(
                link='plugins:netbox_swim:device_bulk_upgrade',
                link_text='Bulk Auto-Remediation',
                permissions=['netbox_swim.add_upgradejob'],
            ),
        )),
    ),
    icon_class='mdi mdi-rocket-launch',
)
