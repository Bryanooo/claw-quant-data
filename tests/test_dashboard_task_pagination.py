from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node is required for dashboard JavaScript regression')
def test_task_directory_reads_all_backend_pages():
    root = Path(__file__).resolve().parents[1]
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('service/dashboard/dashboard.js', 'utf8');
const fn = source.slice(source.indexOf('async function loadTasks('), source.indexOf('async function loadExecutions('));
let calls = [], rendered = 0;
const context = {URLSearchParams, state:{tasks:{page:1,size:30,items:null}},
  $: id => ({value: id === 'taskLifecycle' ? 'active' : ''}),
  renderTaskRows: () => {rendered++;},
  api: async url => {
    calls.push(url);
    return calls.length === 1
      ? {items:Array.from({length:200},(_,i)=>({task_definition_id:i+4})),page:{next_cursor:4}}
      : {items:[{task_definition_id:3},{task_definition_id:2},{task_definition_id:1}],page:{next_cursor:null}};
  }};
vm.createContext(context); vm.runInContext(fn,context);
context.loadTasks().then(()=>{
  assert.equal(context.state.tasks.items.length,203);
  assert.equal(calls.length,2);
  assert(calls[1].includes('before_id=4'));
  assert(calls.every(url=>url.includes('lifecycle_status=active')));
  assert.equal(rendered,1);
}).catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run(['node', '-e', script], cwd=root, check=True, capture_output=True, text=True)
