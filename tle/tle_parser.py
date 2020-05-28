import os
import sys
import logging
from termcolor import colored
import pandas as pd
from bisect import bisect_left, bisect_right
from typing import Tuple
from datetime import datetime, timedelta
from skyfield import api as sf
from skyfield.api import EarthSatellite

from ampyutils import amutils
import am_config as amc


def read_norad2prn(logger: logging.Logger) -> pd.DataFrame:
    """
    read_norad2prn reads the files NORAD-PRN.t and gps-ops-NORAD-PRN.t from dir ~/RxTURP/BEGPIOS/tle connecting NORAD number to PRN (period 2018-2020)
    """
    cFuncName = colored(os.path.basename(__file__), 'yellow') + ' - ' + colored(sys._getframe().f_code.co_name, 'green')

    # create the dictionary with dataframes to return
    column_names = ['GNSS', 'SV-ID', 'PRN', 'NORAD', 'launch']

    # read the NORAD2PRN file in dataframes
    norad2prn_file = os.path.join(os.environ['HOME'], 'RxTURP/BEGPIOS/tle', 'gnss-NORAD-PRN.t')

    try:
        dfNorad = pd.read_csv(norad2prn_file, header=None, names=column_names)
        amutils.logHeadTailDataFrame(logger=logger, callerName=cFuncName, df=dfNorad, dfName='dfNorad')
        return dfNorad
    except NameError as e:
        logger.error('{func:s}: name error occured:\n {err!s}'.format(err=e, func=cFuncName))
        sys.exit(amc.E_FILE_NOT_EXIST)
    except IOError as e:
        logger.error('{func:s}: IO error occured:\n {err!s}'.format(err=e, func=cFuncName))
        sys.exit(amc.E_OSERROR)
    except Exception as e:
        logger.error('{func:s}: error occured \n{err!s}'.format(err=e, func=cFuncName))
        sys.exit(amc.E_FAILURE)


def get_norad_numbers(prns: list, dfNorad: pd.DataFrame, logger: logging.Logger) -> dict:
    """
    get_norad_number returns the NORAD number for a fiven PRN
    """
    cFuncName = colored(os.path.basename(__file__), 'yellow') + ' - ' + colored(sys._getframe().f_code.co_name, 'green')

    # create dict of NORAD numbers corresponding to the given PRNs
    dNorads = {}
    for _, prn in enumerate(prns):
        try:
            dNorads[prn] = dfNorad[dfNorad['PRN'] == prn]['NORAD'].item()
        except ValueError:
            logger.warning('{func:s}: PRN {prn:s} has no corresponding NORAD entry'.format(prn=colored(prn, 'yellow'), func=cFuncName))
            dNorads[prn] = ''

    logger.info('{func:s}: correponding PRN / NORAD numbers = {norad!s}'.format(norad=dNorads, func=cFuncName))

    return dNorads


def find_norad_tle_yydoy(dNorads: dict, yydoy: str, logger: logging.Logger) -> pd.DataFrame:
    """
    find_norad_tle_yydoy finds the corresponding YYDOY entry in the NORAD combined TLEs
    """
    cFuncName = colored(os.path.basename(__file__), 'yellow') + ' - ' + colored(sys._getframe().f_code.co_name, 'green')

    # create dataframe that will hold the PRN, NORAD and TLE lines for each PRN
    df_tle = pd.DataFrame(columns=['PRN', 'NORAD', 'TLE1', 'TLE2'])

    # reading the TLE per SV
    for prn, norad in dNorads.items():
        if norad != '':  # no TLE file available for this PRN
            norad_tle_file = os.path.join(os.environ['HOME'], 'RxTURP/BEGPIOS/tle', 'sat{norad:s}.txt'.format(norad=norad[:-1]))
            logger.info('{func:s}: reading TLE file {name:s} for NORAD ID {norad:s} (PRN={prn:s})'.format(norad=colored(norad, 'green'), prn=colored(prn, 'green'), name=norad_tle_file, func=cFuncName))

            try:
                df_tle_prn = pd.read_csv(norad_tle_file, header=None, delim_whitespace=True)
                amutils.logHeadTailDataFrame(logger=logger, callerName=cFuncName, df=df_tle_prn, dfName='df_tle_prn')

                # # look into rows with first column 1 (TLE Line 1) for date closest to YYDOY
                # print('yydoy = {:s}'.format(yydoy))
                # print('doy = {:d}'.format(int(yydoy[2:])))
                # print('-' * 50)
                # print(df_tle_prn[df_tle_prn[0] == 1][3])
                # print('-' * 50)
                # print(df_tle_prn[df_tle_prn[0] == 2][3])
                # print('-' * 50)

                tle_line1, tle_line2 = get_closests_tle(df=df_tle_prn[df_tle_prn[0] == 1], col=3, val=int(yydoy), norad_file=norad_tle_file, logger=logger)

                logger.info('{func:s}:   TLE line 1: {tle1:s}'.format(tle1=colored(tle_line1, 'green'), func=cFuncName))
                logger.info('{func:s}:   TLE line 2: {tle2:s}'.format(tle2=colored(tle_line2, 'green'), func=cFuncName))

                # Add a new row at index k with values provided in list
                df_tle.loc[len(df_tle.index)] = [prn, norad, tle_line1, tle_line2]
            except NameError as e:
                logger.error('{func:s}: name error occured:\n {err!s}'.format(err=e, func=cFuncName))
                # sys.exit(amc.E_FILE_NOT_EXIST)
            except IOError as e:
                logger.error('{func:s}: IO error occured:\n {err!s}'.format(err=e, func=cFuncName))
                # sys.exit(amc.E_OSERROR)
            except Exception as e:
                logger.error('{func:s}: error occured \n{err!s}'.format(err=e, func=cFuncName))
                # sys.exit(amc.E_FAILURE)

    amutils.logHeadTailDataFrame(logger=logger, callerName=cFuncName, df=df_tle, dfName='df_tle')

    return df_tle


def rise_set_yydoy(df_tle: pd.DataFrame, yydoy: str, dir_tle: str, logger: logging.Logger) -> pd.DataFrame:
    """
    rise_set_yydoy calculates the rise/set times for GNSS PRNs
    """
    cFuncName = colored(os.path.basename(__file__), 'yellow') + ' - ' + colored(sys._getframe().f_code.co_name, 'green')

    # get the datetime that corresponds to yydoy
    date_yydoy = datetime.strptime(yydoy, '%y%j')
    logger.info('{func:s}: calculating rise / set times for {date:s} ({yy:s}/{doy:s})'.format(date=colored(date_yydoy.strftime('%d-%m-%Y'), 'green'), yy=yydoy[:2], doy=yydoy[2:], func=cFuncName))

    # load a time scale and set RMA as Topo
    # loader = sf.Loader(dir_tle, expire=True)  # loads the needed data files into the tle dir
    ts = sf.load.timescale()
    RMA = sf.Topos('50.8438 N', '4.3928 E')
    logger.info('{func:s}: Earth station RMA = {topo!s}'.format(topo=colored(RMA, 'green'), func=cFuncName))

    t0 = ts.utc(int(date_yydoy.strftime('%Y')), int(date_yydoy.strftime('%m')), int(date_yydoy.strftime('%d')))
    date_tomorrow = date_yydoy + timedelta(days=1)
    t1 = ts.utc(int(date_tomorrow.strftime('%Y')), int(date_tomorrow.strftime('%m')), int(date_tomorrow.strftime('%d')))

    # go over the PRN / NORADs that have TLE corresponding to the requested date
    for row, prn in enumerate(df_tle['PRN']):
        logger.info('{func:s}:   for NORAD {norad:s} ({prn:s})'.format(norad=colored(df_tle['NORAD'][row], 'green'), prn=colored(prn, 'green'), func=cFuncName))
        # create a EarthSatellites from the TLE lines for this PRN
        gnss_sv = EarthSatellite(df_tle['TLE1'][row], df_tle['TLE2'][row])
        logger.info('{func:s}:       created erath satellites {sat!s}'.format(sat=colored(gnss_sv, 'green'), func=cFuncName))

        t, events = gnss_sv.find_events(RMA, t0, t1, altitude_degrees=5.0)

        for ti, event in zip(t, events):
            name = ('rise above 5d', 'culminate', 'set below 5d')[event]
            logger.info('{func:s}:         {jpl!s} -- {name!s}'.format(jpl=ti.utc_jpl(), name=name, func=cFuncName))


def get_closests(df: pd.DataFrame, col: int, val: int) -> Tuple[int, int]:
    lower_idx = bisect_left(df[col].values, val)
    higher_idx = bisect_right(df[col].values, val)
    if higher_idx == lower_idx:      # val is not in the list
        return lower_idx - 1, lower_idx
    else:                            # val is in the list
        return lower_idx, lower_idx


def get_closests_tle(df: pd.DataFrame, col: int, val: int, norad_file: str, logger: logging.Logger) -> Tuple[str, str, int]:
    """
    get_closests_tle scans the TLE files and returns those closest to epoch
    """
    cFuncName = colored(os.path.basename(__file__), 'yellow') + ' - ' + colored(sys._getframe().f_code.co_name, 'green')

    df_sort = df.iloc[(df[col] - val).abs().argsort()[:1]]
    tle1_idx = df_sort.index.tolist()[0]

    # read the 2 lines from the file
    with open(norad_file) as fp:
        for i, line in enumerate(fp):
            if i == tle1_idx:
                tle_line1 = line
            elif i == tle1_idx + 1:
                tle_line2 = line
            elif i > tle1_idx + 1:
                break

    logger.debug('{func:s}: found TLE1: {tle1!s}'.format(tle1=tle_line1[:-1], func=cFuncName))
    logger.debug('{func:s}: found TLE2: {tle2!s}'.format(tle2=tle_line2[:-1], func=cFuncName))

    return tle_line1[:-1], tle_line2[:-1]


def take_closest(num: float, collection: list):
    return min(collection, key=lambda x: abs(x - num))