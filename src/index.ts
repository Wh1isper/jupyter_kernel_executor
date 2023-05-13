import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {NotebookPanel} from '@jupyterlab/notebook';
import {RunBackendExtension} from './extension'

/**
 * Initialization data for the jupyter_kernel_executor extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyter_kernel_executor:plugin',
  autoStart: true,
  activate: (
    app: JupyterFrontEnd,
    panel: NotebookPanel,
  ) => {

    app.docRegistry.addWidgetExtension(
      'Notebook',
      new RunBackendExtension(
        app,
        panel
      )
    );
    console.log('JupyterLab extension jupyter_kernel_executor is activated!');
  }
};

export default plugin;
