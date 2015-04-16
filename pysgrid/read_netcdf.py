'''
Created on Mar 19, 2015

@author: ayan
'''
import netCDF4 as nc4
from .custom_exceptions import SGridNonCompliantError, deprecated
from .utils import ParsePadding, pair_arrays, determine_variable_slicing
from .variables import SGridVariable
from .lookup import (LAT_GRID_CELL_CENTER_LONG_NAME, LON_GRID_CELL_CENTER_LONG_NAME,
                     LAT_GRID_CELL_NODE_LONG_NAME, LON_GRID_CELL_NODE_LONG_NAME)


def read_netcdf_file(dataset_url):
    """
    Read a netCDF file into a dataset
    object.
    
    :param str dataset_url: path or URL to a netCDF file
    :return: netCDF dataset object
    :rtype: netCDF4.Dataset
    
    """
    nc_dataset = nc4.Dataset(dataset_url)
    return nc_dataset


class NetCDFDataset(object):
    
    def __init__(self, nc_dataset_obj):
        self.ncd = nc_dataset_obj
    
    @deprecated
    def find_grid_cell_center_vars(self):
        """
        Find the variables for the grid
        cell centers.
        
        """
        nc_vars = self.ncd.variables
        grid_cell_center_lon = None
        grid_cell_center_lat = None
        for nc_var in nc_vars.keys():
            try:
                nc_var_obj = nc_vars[nc_var]
                # need to revisit this... long_name is not a required attribute
                nc_var_long_name = nc_var_obj.long_name
                if nc_var_long_name in LON_GRID_CELL_CENTER_LONG_NAME:
                    grid_cell_center_lon = nc_var
                if nc_var_long_name in LAT_GRID_CELL_CENTER_LONG_NAME:
                    grid_cell_center_lat = nc_var
            except AttributeError:
                continue
        return grid_cell_center_lon, grid_cell_center_lat
    
    def find_grid_cell_node_vars(self):
        """
        Find the variables for the grid
        cell vertices.
        
        """
        nc_vars = self.ncd.variables
        grid_cell_node_lon = None
        grid_cell_node_lat = None
        for nc_var in nc_vars.keys():
            try:
                nc_var_obj = nc_vars[nc_var]
                nc_var_long_name = nc_var_obj.long_name
                if nc_var_long_name in LON_GRID_CELL_NODE_LONG_NAME:
                    grid_cell_node_lon = nc_var
                if nc_var_long_name in LAT_GRID_CELL_NODE_LONG_NAME:
                    grid_cell_node_lat = nc_var
            except AttributeError:
                continue
        return grid_cell_node_lon, grid_cell_node_lat
        
    def find_grid_topology_vars(self):
        """
        Get the variables from a netCDF dataset
        that have a cf_role attribute of 'grid_topology'.
        
        :params nc: netCDF dataset
        :type nc: netCDF4.Dataset
        :return: list of variables that contain grid topologies
        :rtype: list
        
        """
        nc_vars = self.ncd.variables
        grid_topology_vars = []
        for nc_var in nc_vars.keys():
            nc_var_obj = nc_vars[nc_var]
            try:
                cf_role = nc_var_obj.cf_role.strip()
                topology_dim = nc_var_obj.topology_dimension
            except AttributeError:
                cf_role = None
                topology_dim = None
            if cf_role == 'grid_topology' and topology_dim >= 2:
                grid_topology_vars.append(nc_var)
        return grid_topology_vars
    
    def search_variables_by_location(self, location_str):
        nc_vars = self.ncd.variables
        search_results = []
        for nc_var in nc_vars.keys():
            nc_var_obj = nc_vars[nc_var]
            try:
                nc_var_location = nc_var_obj.location
                if nc_var_location == location_str:
                    search_results.append(nc_var)
            except AttributeError:
                continue
        return search_results
    
    def find_coordinates_by_location(self, location_str, topology_dim):
        """
        Find a grid coordinates variables with a location attribute equal
        to location_str. This method can be used to infer edge, face, or
        volume coordinates from the location attribute of a variable.
        
        Location is a required attribute per SGRID conventions.
        
        :param str location_str: the location value to search for
        :param int topology_dim: the topology dimension of the grid
        
        """
        nc_vars = self.ncd.variables
        vars_with_location = self.search_variables_by_location(location_str)
        potential_coordinates = []
        for var_with_location in vars_with_location:
            location_var = nc_vars[var_with_location]
            location_var_dims = location_var.dimensions
            for nc_var in nc_vars.keys():
                nc_var_obj = nc_vars[nc_var]
                nc_var_dim_set = set(nc_var_obj.dimensions)
                if (nc_var_dim_set.issubset(location_var_dims) and 
                    nc_var != var_with_location and 
                    len(nc_var_dim_set) > 0
                    ):
                    potential_coordinates.append(nc_var_obj)
        x_coordinate = None
        y_coordinate = None
        z_coordinate = None
        for potential_coordinate in potential_coordinates:
            pc_name = potential_coordinate.name
            if 'lon' in pc_name.lower():
                x_coordinate = pc_name
            elif 'lat' in pc_name.lower():
                y_coordinate = pc_name
            else:
                z_coordinate = pc_name
        if topology_dim == 2:
            coordinates = (x_coordinate, y_coordinate)
        else:
            coordinates = (x_coordinate, y_coordinate, z_coordinate)
        if all(coordinates):
            coordinate_result = coordinates
        else:
            coordinate_result = None
        return coordinate_result
    
    @deprecated
    def find_coordinations_by_location(self, location_str, topology_dim):
        """
        Find a variable with a location attribute equal
        to location_str.
        
        Location is a required attribute per SGRID conventions.
        
        :param str location_str: the location value to search for
        :param int topology_dim: the topology dimension of the grid
        """
        nc_vars = self.ncd.variables
        vars_with_location = self.search_variables_by_location(location_str)
        result = None
        for nc_var in vars_with_location:
            nc_var_obj = nc_vars[nc_var]
            try:
                nc_var_coordinates = nc_var_obj.coordinates
                nc_var_coord_split = nc_var_coordinates.strip().split(' ')
                x_coordinate = None
                y_coordinate = None
                z_coordinate = None
                for nc_var_coord in nc_var_coord_split:
                    var_coord = nc_vars[nc_var_coord]
                    try:
                        var_coord_standard_name = var_coord.standard_name
                        if var_coord_standard_name == 'longitude':
                            x_coordinate = nc_var_coord
                        elif var_coord_standard_name == 'latitude':
                            y_coordinate = nc_var_coord
                    except AttributeError:
                        continue
                if topology_dim == 2:
                    result = (x_coordinate, y_coordinate)
                elif topology_dim == 3:
                    # finding the z_coordinate isn't fully baked yet
                    result = (x_coordinate, y_coordinate, z_coordinate)
                else:
                    raise Exception('I have no idea what to do....')
                break
            except AttributeError:
                result = None
                continue
        return result

    def sgrid_compliant_file(self):
        """
        Determine whether a dataset is
        SGRID compliant.
        
        :param nc: netCDF dataset
        :type nc: netCDF4.Dataset
        :return: True if dataset is compliant, False if it is not
        :rtype: bool
        
        """
        grid_vars = self.find_grid_topology_vars()
        if len(grid_vars) > 0:
            sgrid_compliant = True
        else:
            sgrid_compliant = False
        return sgrid_compliant


def load_grid_from_nc_file(nc_path, grid, grid_topology_vars=None, load_data=True):
    """
    Create a SGRID object from a path to an
    SGRID compliant netCDF resource. An 
    exception is raised if the resource is
    found to be non-compliant.
    
    :param str nc_path: path to the resource; this can be a filepath or a URL
    :param grid: an SGRID object
    :type grid: sgrid.SGrid
    :return: an SGrid object
    :rtype: sgrid.SGrid
    
    """
    with nc4.Dataset(nc_path, 'r') as nc_dataset:
        grid = load_grid_from_nc_dataset(nc_dataset, grid, 
                                         grid_topology_vars=grid_topology_vars, 
                                         load_data=load_data
                                         )
    return grid


def load_grid_from_nc_dataset(nc_dataset, grid, 
                              grid_topology_vars=None, 
                              load_data=True):
    """
    Create an SGRID object from an SGRID
    compliant netCDF4.Dataset object. An
    exception is raised if the dataset is
    non-compliant.
    
    :param nc_dataset: a netCDF resource read into a netCDF4.Dataset object
    :type nc_dataset: netCDF4.Dataset
    :param grid: an SGRID object
    :type grid: sgrid.SGrid
    :return: an SGrid object
    :rtype: sgrid.SGrid
    
    """
    ncd = NetCDFDataset(nc_dataset)
    is_sgrid_compliant = ncd.sgrid_compliant_file()
    if is_sgrid_compliant:
        ds_dims = nc_dataset.dimensions
        grid_dims = [(ds_dim, len(ds_dims[ds_dim])) for ds_dim in ds_dims]
        grid.dimensions = grid_dims
        if grid_topology_vars is None:
            grid_topology_vars_attr = ncd.find_grid_topology_vars()
        else:
            grid_topology_vars_attr = grid_topology_vars
        grid.grid_topology_vars = grid_topology_vars_attr  # set grid variables
        for topology_var in grid_topology_vars_attr:
            nc_grid_topology_var = nc_dataset.variables[topology_var]
            pp = ParsePadding(topology_var)
            topology_dim = nc_grid_topology_var.topology_dimension
            grid.topology_dimension = topology_dim
            try:
                # this gets run through if topology_dimension is 2
                face_dim = nc_grid_topology_var.face_dimensions
                face_dim_padding = pp.parse_padding(face_dim)
                grid.face_dimensions = face_dim
                grid.face_padding = face_dim_padding  # set face padding
            except AttributeError:
                pass
            try:
                # this gets run through if topology_dimension is 3
                vol_dim = nc_grid_topology_var.volume_dimensions
                vol_dim_padding = pp.parse_padding(vol_dim)
                grid.volume_dimensions = vol_dim
                grid.volume_padding = vol_dim_padding
            except AttributeError:
                pass
            try:
                edge1_dim = nc_grid_topology_var.edge1_dimensions
                edge1_dim_padding = pp.parse_padding(edge1_dim)
                grid.edge_1_dimension = edge1_dim
                grid.edge_1_padding = edge1_dim_padding  # set edge 1 padding
            except AttributeError:
                pass
            try:
                edge2_dim = nc_grid_topology_var.edge2_dimensions
                edge2_dim_padding = pp.parse_padding(edge2_dim)
                grid.edge_2_dimensions = edge2_dim
                grid.edge_2_padding = edge2_dim_padding  # set edge 2 padding
            except AttributeError:
                pass
            try:
                vertical_dim = nc_grid_topology_var.vertical_dimensions
                vertical_dim_padding = pp.parse_padding(vertical_dim)
                grid.vertical_dimensions = vertical_dim
                grid.vertical_padding = vertical_dim_padding  # set vertical padding
            except AttributeError:
                pass
            if topology_dim == 3:
                try:
                    volume_coordinates = nc_grid_topology_var.volume_coordinates
                    volume_coordinate_val = volume_coordinates.split(' ')
                    grid.volume_coordinates = volume_coordinate_val
                except AttributeError:
                    grid_cell_center_vars = ncd.find_coordinates_by_location('volume', topology_dim)
                    grid.volume_coordinates = grid_cell_center_vars
            if topology_dim == 2:
                try:
                    face_coordinates = nc_grid_topology_var.face_coordinates
                    face_coordinate_val = face_coordinates.split(' ')
                    grid.face_coordinates = tuple(face_coordinate_val)
                except AttributeError:
                    grid_cell_center_vars = ncd.find_coordinates_by_location('face', topology_dim)
                    grid.face_coordinates = grid_cell_center_vars
            try:
                node_coordinates = nc_grid_topology_var.node_coordinates
                node_coordinate_val = node_coordinates.split(' ')
                grid.node_coordinates = tuple(node_coordinate_val)
            except AttributeError:
                grid_cell_node_vars = ncd.find_grid_cell_node_vars()
                grid.node_coordinates = grid_cell_node_vars
            try:
                edge_1_coordinates = nc_grid_topology_var.edge1_coordinates
                edge_1_coordinates_val = edge_1_coordinates.split(' ')
                grid.edge_1_coordinates = tuple(edge_1_coordinates_val)
            except AttributeError:
                edge_1_coordinates_val = ncd.find_coordinates_by_location('edge1', topology_dim)
                grid.edge_1_coordinates = edge_1_coordinates_val
            try:
                edge_2_coordinates = nc_grid_topology_var.edge2_coordinates
                edge_2_coordinates_val = edge_2_coordinates.split(' ')
                grid.edge_2_coordinates = tuple(edge_2_coordinates_val)
            except AttributeError:
                edge_2_coordinates_val = ncd.find_coordinates_by_location('edge2', topology_dim)
                grid.edge_2_coordinates = edge_2_coordinates_val
        if grid.topology_dimension == 2:
            grid_cell_center_lon_var, grid_cell_center_lat_var = grid.face_coordinates
        elif grid.topology_dimension == 3:
            grid_cell_center_lon_var = grid.volume_coordinates[0]
            grid_cell_center_lat_var = grid.volume_coordinates[1]
        grid_cell_center_lat = nc_dataset.variables[grid_cell_center_lat_var][:]
        grid_cell_center_lon = nc_dataset.variables[grid_cell_center_lon_var][:]
        grid.centers = pair_arrays(grid_cell_center_lon, grid_cell_center_lat)
        # get the variables names for the cell vertices
        grid_cell_nodes_lat_var, grid_cell_nodes_lon_var = grid.node_coordinates
        grid_cell_nodes_lat = nc_dataset.variables[grid_cell_nodes_lat_var][:]
        grid_cell_nodes_lon = nc_dataset.variables[grid_cell_nodes_lon_var][:]
        grid.nodes = pair_arrays(grid_cell_nodes_lon, grid_cell_nodes_lat)
        grid.node_dimensions = nc_grid_topology_var.node_dimensions
        # get time data
        grid_time = nc_dataset.variables['time'][:]
        nc_variables = nc_dataset.variables
        # provide a list of all variables in the netCDF dataset
        grid.grid_times = grid_time
        dataset_variables = []
        grid_variables = []
        for nc_variable in nc_variables:
            nc_var = nc_variables[nc_variable]
            nc_var_name = nc_var.name
            # ds_var = (nc_var_name, nc_var_dtype, nc_var_dims)
            dataset_variables.append(nc_var_name)
            try:
                # figure out if a variable is defined on the grid
                if nc_var.grid:
                    grid_variables.append(nc_var_name)
            except AttributeError:
                continue
        grid.variables = dataset_variables
        grid.grid_variables = grid_variables
        # provide the angles
        try:
            grid_angles = nc_dataset.variables['angle'][:]
            grid.angles = grid_angles
        except KeyError:
            pass
        # dynamically set variable attributes
        for nc_variable in nc_variables:
            nc_var_obj = nc_variables[nc_variable]
            sgrid_var = SGridVariable.create_variable(nc_var_obj)
            var_center_slicing = determine_variable_slicing(grid, nc_dataset, 
                                                            nc_variable, method='center'
                                                            )
            sgrid_var.center_slicing = var_center_slicing
            grid.add_property(sgrid_var.variable, sgrid_var)
        return grid
    else:
        raise SGridNonCompliantError(nc_dataset)