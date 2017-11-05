from edisgo.grid.components import Storage, Line
from edisgo.grid.tools import select_cable

import logging

def integrate_storage(network, position, operation):
    """
    Integrate storage units in the grid and specify its operational mode

    Parameters
    ----------
    network: :class:`~.grid.network.Network`
            The eDisGo container object
    position : str
        Specify storage location. Available options are
         * 'hvmv_substation_busbar'
    operation : str
        Specify mode of storage operation
    """

    if position == 'hvmv_substation_busbar':
        storage_at_hvmv_substation(network.mv_grid)
    else:
        logging.error("{} is not a valid storage positioning mode".format(
            position))
        raise ValueError("Unknown parameter for storage posisitioning: {} is "
                         "not a valid storage positioning mode".format(
            position))


def storage_at_hvmv_substation(mv_grid, nominal_capacity=1000):
    """
    Place 1 MVA battery at HV/MV substation bus bar

    As this is currently a dummy implementation the storage operation is as
    simple as follows:
     * Feedin > 50 % -> charge at full power
     * Feedin < 50 % -> discharge at full power

    Parameters
    ----------
    mv_grid : :class:`~.grid.grids.MVGrid`
        MV grid instance
    nominal_capacity : float
        Storage's apparent rated power
    """

    # define storage instance and define it's operational mode
    storage_id = len(mv_grid.graph.nodes_by_attribute('storage')) + 1
    storage = Storage(operation={'mode': 'fifty-fifty'},
                      id=storage_id,
                      nominal_capacity=nominal_capacity)

    # add storage itself to graph
    mv_grid.graph.add_nodes_from(storage, type='storage')

    # add 1m connecting line to hv/mv substation bus bar
    line_type, _ = select_cable(mv_grid.network, 'mv', nominal_capacity)
    line = [mv_grid.station, storage,
              {'line': Line(
                  id=storage_id,
                  type=line_type,
                  kind='cable',
                  length=1,
                  grid=mv_grid)
              }]
    mv_grid.graph.add_edges_from(line, type='line')