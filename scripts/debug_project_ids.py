from scrum_kitchen_metrics.config import GitLabSettings

print('Annotation:', GitLabSettings.model_fields['project_ids'].annotation)
print('Origin:', getattr(GitLabSettings.model_fields['project_ids'].annotation, '__origin__', None))
