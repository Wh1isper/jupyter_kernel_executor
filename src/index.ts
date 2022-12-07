import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

/**
 * Initialization data for the jupyter_kernel_executor extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyter_kernel_executor:plugin',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension jupyter_kernel_executor is activated!');
  }
};

export default plugin;
