import numpy as np
#import netCDF4 as nc
from scipy.io import netcdf as nc
import sys

### File I/O ###
# This class is prepared by Tony Qian (tqian@pppl.gov)
# the original file included reading options for netCDF and binary
# these have been removed and the code only writes netCDF
#
# updated 15 November 2021


class MGRID():

    def __init__(self, fname='temp', binary=False,\
                 nr=51, nz=51, nphi=24, nfp=2,\
                 rmin=0.20, rmax=0.40, zmin=-0.10, zmax=0.10,\
                 nextcur=0):

        self.nr = nr
        self.nz = nz
        self.nphi = nphi
        self.nfp = nfp

        self.rmin = rmin
        self.rmax = rmax
        self.zmin = zmin
        self.zmax = zmax

        self.n_ext_cur = 0
        self.cur_labels = []

        self.br_arr = [] 
        self.bz_arr = [] 
        self.bp_arr = [] 

        print('Initialized mgrid file: (nr,nphi,nz,nfp) = ({}, {}, {}, {})'.format(nr, nphi, nz, nfp))

    def add_field_cylindrical(self, br, bp, bz, name='default'):

        # structure Bfield data into arrays (phi,z,r) arrays

        self.br_arr.append(br)
        self.bz_arr.append(bz)
        self.bp_arr.append(bp)

        # add coil label
        if (name == 'default'):
            label = pad_string('magnet_%i' % self.n_ext_cur)
        else:
            label = pad_string(name)
        self.cur_labels.append(label)
        self.n_ext_cur = self.n_ext_cur + 1

    def write(self, fout):

        ### Write
        print('Writing mgrid file')
        #ds = nc.Dataset(fout, 'w', format='NETCDF4')
        ds = nc.netcdf_file(fout, 'w')

        # set dimensions
        ds.createDimension('stringsize', 30)
        ds.createDimension('dim_00001', 1)
        ds.createDimension('external_coil_groups', self.n_ext_cur)
        ds.createDimension('external_coils', self.n_ext_cur)
        ds.createDimension('rad', self.nr)
        ds.createDimension('zee', self.nz)
        ds.createDimension('phi', self.nphi)

        # declare variables
        var_ir = ds.createVariable('ir', 'i4', ('dim_00001',))
        var_jz = ds.createVariable('jz', 'i4', ('dim_00001',))
        var_kp = ds.createVariable('kp', 'i4', ('dim_00001',))
        var_nfp = ds.createVariable('nfp', 'i4', ('dim_00001',))
        var_nextcur = ds.createVariable('nextcur', 'i4', ('dim_00001',))

        var_rmin = ds.createVariable('rmin', 'f8', ('dim_00001',))
        var_zmin = ds.createVariable('zmin', 'f8', ('dim_00001',))
        var_rmax = ds.createVariable('rmax', 'f8', ('dim_00001',))
        var_zmax = ds.createVariable('zmax', 'f8', ('dim_00001',))

        var_coil_group = ds.createVariable('coil_group', 'c', ('external_coil_groups', 'stringsize',))
        var_mgrid_mode = ds.createVariable('mgrid_mode', 'c', ('dim_00001',))
        var_raw_coil_cur = ds.createVariable('raw_coil_cur', 'f8', ('external_coils',))

        # assign values
        var_ir[:] = self.nr
        var_jz[:] = self.nz
        var_kp[:] = self.nphi
        var_nfp[:] = self.nfp
        var_nextcur[:] = self.n_ext_cur

        var_rmin[:] = self.rmin
        var_zmin[:] = self.zmin
        var_rmax[:] = self.rmax
        var_zmax[:] = self.zmax

        var_coil_group[:] = self.cur_labels
        var_mgrid_mode[:] = 'N'  # R - Raw, S - scaled, N - none (old version)
        var_raw_coil_cur[:] = np.ones(self.n_ext_cur)

        # add fields
        for j in np.arange(self.n_ext_cur):

            tag = '_%.3i' % (j+1)
            var_br_001 = ds.createVariable('br'+tag, 'f8', ('phi', 'zee', 'rad'))
            var_bp_001 = ds.createVariable('bp'+tag, 'f8', ('phi', 'zee', 'rad'))
            var_bz_001 = ds.createVariable('bz'+tag, 'f8', ('phi', 'zee', 'rad'))

            var_br_001[:, :, :] = self.br_arr[j]
            var_bz_001[:, :, :] = self.bz_arr[j]
            var_bp_001[:, :, :] = self.bp_arr[j]

        ds.close()

        print('  Wrote to file:', fout)

    def export_phi(self):
        phi = np.linspace(0, 2*np.pi/self.nfp, self.nphi)
        return phi

    def export_grid_spacing(self):
        return self.nr, self.nz, self.nphi


### for writing coil groups
def pad_string(string):
    return '{:^30}'.format(string).replace(' ', '_')


### for reading coil groups
def unpack(binary_array):
    return "".join(np.char.decode(binary_array)).strip()


class ReadMGRID():

    def __init__(self, fin):

        self.data = nc.netcdf_file(fin, 'r') 

        # store name
        fname = "".join(fin.split('/')[-1].split('.')[1:-1])
        if (fname == ""):
            fname = "".join(fin.split('_')[1:])
        self.fname = fname

        self.load_data()

    def load_data(self):

        f = self.data

        self.nextcur = int(f.variables['nextcur'].getValue())
        coil_data = f.variables['coil_group'][:]
        self.coil_names = [unpack(coil_data[j]) for j in range(self.nextcur)] 

        self.rmin = f.variables['rmin'].getValue()
        self.rmax = f.variables['rmax'].getValue()
        self.zmin = f.variables['zmin'].getValue()
        self.zmax = f.variables['zmax'].getValue()
        self.nr = f.variables['ir']    .getValue()
        self.nz = f.variables['jz']    .getValue()
        self.nphi = f.variables['kp']  .getValue()

        self.rax = np.linspace(self.rmin, self.rmax, self.nr)
        self.zax = np.linspace(self.zmin, self.zmax, self.nz)

        self.mode = f.variables['mgrid_mode'][:][0].decode()
        self.raw_coil_current = np.array(f.variables['raw_coil_cur'][:])

        br_arr = []
        bp_arr = []
        bz_arr = []

        nextcur = self.nextcur
        for j in range(nextcur):
            idx = '{:03d}'.format(j+1)
            br = f.variables['br_'+idx][:]  # phi z r
            bp = f.variables['bp_'+idx][:]
            bz = f.variables['bz_'+idx][:]

            if (self.mode == 'S'):
                br_arr.append(br * self.raw_coil_current[j])
                bp_arr.append(bp * self.raw_coil_current[j])
                bz_arr.append(bz * self.raw_coil_current[j])
            else:
                br_arr.append(br)
                bp_arr.append(bp)
                bz_arr.append(bz)

        self.br_arr = np.array(br_arr)
        self.bp_arr = np.array(bp_arr)
        self.bz_arr = np.array(bz_arr)

        # sum over coil groups
        if nextcur > 1:
            br = np.sum(br_arr, axis=0)
            bp = np.sum(bp_arr, axis=0)
            bz = np.sum(bz_arr, axis=0)
        else:
            br = br_arr[0]
            bp = bp_arr[0]
            bz = bz_arr[0]

        self.br = br
        self.bp = bp
        self.bz = bz

        self.bvec = np.transpose([br, bp, bz])

    # jphi - an index on the phi slice
    # k    - which column of subplots to plot in
    # fig,axs - subplot handles
    def plot_mgrid(self, jphi, k, fig, axs, bscale=0):

        rax = self.rax
        zax = self.zax

        subplot_slice(np.s_[0, k], self.br[jphi], rax, zax, tag='br', bscale=bscale)
        subplot_slice(np.s_[1, k], self.bp[jphi], rax, zax, tag='bp', bscale=bscale)
        subplot_slice(np.s_[2, k], self.bz[jphi], rax, zax, tag='bz', bscale=bscale)

        axs[0, k].set_title(self.fname)
        axs[1, k].set_title('nextcur = {}, mode {}'.format(self.nextcur, self.mode), fontsize=10)
        axs[2, k].set_title('nr,np,nz = ({},{},{})'.format(self.nr, self.nphi, self.nz), fontsize=10)

