from netbox.plugins import PluginTemplateExtension
from django.urls import reverse

class DeviceSyncButton(PluginTemplateExtension):
    models = ['dcim.device']
    
    def buttons(self):
        obj = self.context['object']
        if obj._meta.label_lower != 'dcim.device':
            return ""
        device = obj
        # The URL in urls.py is plugins:netbox_swim:device_sync which resolves to device/<int:pk>/sync/
        url = reverse('plugins:netbox_swim:device_sync', args=[device.pk])
        return f"""
        <form action="{url}" method="post" class="d-inline">
            <input type="hidden" name="csrfmiddlewaretoken" value="{self.context['csrf_token']}">
            <button type="submit" class="btn btn-sm btn-primary">
                <i class="mdi mdi-sync"></i> Sync SWIM Facts
            </button>
        </form>
        """

    def right_page(self):
        from .models import DeviceSyncRecord
        obj = self.context['object']
        if obj._meta.label_lower != 'dcim.device':
            return ""
        device = obj
        records = DeviceSyncRecord.objects.filter(device=device).order_by('-created')[:5]
        
        if not records:
            return ""
            
        html = """
        <div class="card">
            <h5 class="card-header">Recent Live SWIM Sync Diffs</h5>
            <div class="card-body">
                <table class="table table-hover attr-table">
                    <tr><th>Date</th><th>Status</th><th>Detected Changes</th></tr>
        """
        for r in records:
            diff_text = ""
            if r.detected_diff:
                for k, v in r.detected_diff.items():
                    diff_text += f"<b>{k}:</b> {str(v.get('old'))} &rarr; {str(v.get('new'))}<br>"
            
            badge_class = "bg-primary"
            if r.status in ['auto_applied', 'applied']: badge_class = 'bg-success'
            elif r.status == 'failed': badge_class = 'bg-danger'
            elif r.status == 'pending': badge_class = 'bg-warning text-dark'

            html += f"""
                <tr>
                    <td>{r.created.strftime('%Y-%m-%d %H:%M')}</td>
                    <td><span class="badge {badge_class}">{r.get_status_display()}</span></td>
                    <td>{diff_text if diff_text else '<em>No differences found</em>'}</td>
                </tr>
            """
        html += """
                </table>
            </div>
        </div>
        """
        return html

template_extensions = [DeviceSyncButton]
