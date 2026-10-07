import os
import re

file_path = os.path.join(os.getcwd(), 'core', 'pipeline.py')
with open(file_path, 'r') as f:
    content = f.read()

content = content.replace(
    'asyncio.create_task(self._update_baseline(event, baseline))',
    'await self._update_baseline(event, baseline)  # Synchronous for tests'
)

with open(file_path, 'w') as f:
    f.write(content)

