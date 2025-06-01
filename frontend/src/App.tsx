import { useState } from 'react'
import { 
  Container, 
  Typography, 
  Box, 
  Paper, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow,
  CircularProgress,
  useTheme,
  useMediaQuery,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Alert,
  IconButton,
  Tooltip,
  ThemeProvider,
  createTheme,
  Skeleton,
  Chip,
  alpha
} from '@mui/material'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import axios from 'axios'
import RefreshIcon from '@mui/icons-material/Refresh'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import InfoIcon from '@mui/icons-material/Info'

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
  components: {
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
          },
        },
      },
    },
  },
})

const queryClient = new QueryClient()

interface Prop {
  player_name: string
  prop_type: string
  line: number
  prizepicks_odds: number
  pinnacle_over: number
  pinnacle_under: number
  no_vig_over: number
  no_vig_under: number
}

type SortField = 'player_name' | 'prop_type' | 'line' | 'prizepicks_odds' | 'pinnacle_over' | 'pinnacle_under' | 'no_vig_over' | 'no_vig_under'
type SortDirection = 'asc' | 'desc'

interface PropsData {
  props: Prop[];
  disclaimer?: string;
  last_updated: string;
  status?: string;
}

function LoadingSkeleton() {
  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ mb: 2, display: 'flex', gap: 2 }}>
        <Skeleton variant="rectangular" width={200} height={40} />
        <Skeleton variant="rectangular" width={200} height={40} />
      </Box>
      <Skeleton variant="rectangular" height={400} />
    </Box>
  )
}

function OddsComparison({ prizepicks, pinnacleOver, pinnacleUnder }: { prizepicks: number, pinnacleOver: number, pinnacleUnder: number }) {
  const overDiff = prizepicks - pinnacleOver
  const underDiff = prizepicks - pinnacleUnder
  const isOverBetter = overDiff > 0
  const isUnderBetter = underDiff > 0
  
  return (
    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
      <Tooltip title={`Over: ${isOverBetter ? 'Better' : 'Worse'} by ${Math.abs(overDiff).toFixed(2)}`}>
        <Chip
          icon={isOverBetter ? <TrendingUpIcon /> : <TrendingDownIcon />}
          label={`O ${isOverBetter ? '+' : ''}${overDiff.toFixed(2)}`}
          size="small"
          color={isOverBetter ? 'success' : 'error'}
        />
      </Tooltip>
      <Tooltip title={`Under: ${isUnderBetter ? 'Better' : 'Worse'} by ${Math.abs(underDiff).toFixed(2)}`}>
        <Chip
          icon={isUnderBetter ? <TrendingUpIcon /> : <TrendingDownIcon />}
          label={`U ${isUnderBetter ? '+' : ''}${underDiff.toFixed(2)}`}
          size="small"
          color={isUnderBetter ? 'success' : 'error'}
        />
      </Tooltip>
    </Box>
  )
}

function PropsTable() {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedPropType, setSelectedPropType] = useState<string>('all')
  const [sortField, setSortField] = useState<keyof Prop>('no_vig_over')
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">('desc')
  const [lastUpdated, setLastUpdated] = useState<string>('')

  const { data, isLoading, error, refetch } = useQuery<PropsData>({
    queryKey: ['props'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/props')
      if (!response.ok) {
        throw new Error('Network response was not ok')
      }
      const data = await response.json()
      if (data.last_updated) {
        setLastUpdated(new Date(data.last_updated * 1000).toLocaleTimeString())
      }
      return data
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  })

  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const filteredAndSortedData = data?.props
    ?.filter(prop => 
      prop.player_name.toLowerCase().includes(searchTerm.toLowerCase()) &&
      (selectedPropType === 'all' || prop.prop_type === selectedPropType)
    )
    .sort((a, b) => {
      const aValue = a[sortField]
      const bValue = b[sortField]
      
      if (aValue === null) return 1
      if (bValue === null) return -1
      
      const comparison = aValue < bValue ? -1 : aValue > bValue ? 1 : 0
      return sortDirection === 'asc' ? comparison : -comparison
    })

  const uniquePropTypes = Array.from(new Set(data?.props?.map(prop => prop.prop_type) || []))

  if (isLoading) {
    return <LoadingSkeleton />
  }

  if (error) {
    return (
      <Box sx={{ mt: 2 }}>
        <Alert 
          severity="error" 
          action={
            <Button color="inherit" size="small" onClick={() => {}}>
              Retry
            </Button>
          }
        >
          Error loading props data
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            label="Search Players"
            variant="outlined"
            size="small"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            sx={{ minWidth: 200 }}
          />
          
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Prop Type</InputLabel>
            <Select
              value={selectedPropType}
              label="Prop Type"
              onChange={(e) => setSelectedPropType(e.target.value)}
            >
              <MenuItem value="all">All Props</MenuItem>
              <MenuItem value="Strikeouts">Strikeouts</MenuItem>
              <MenuItem value="Hits">Hits</MenuItem>
              <MenuItem value="Total Bases">Total Bases</MenuItem>
              <MenuItem value="RBI">RBI</MenuItem>
              <MenuItem value="Home Runs">Home Runs</MenuItem>
              <MenuItem value="Walks">Walks</MenuItem>
              <MenuItem value="Stolen Bases">Stolen Bases</MenuItem>
              <MenuItem value="Pitching Strikeouts">Pitching Strikeouts</MenuItem>
              <MenuItem value="Earned Runs">Earned Runs</MenuItem>
              <MenuItem value="Innings Pitched">Innings Pitched</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {lastUpdated && (
            <Typography variant="body2" color="text.secondary">
              Last updated: {lastUpdated}
            </Typography>
          )}
          <Tooltip title="Refresh Data">
            <IconButton onClick={() => refetch()} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Compare odds between PrizePicks and Pinnacle to find the best value">
            <IconButton color="info">
              <InfoIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <TableContainer 
        component={Paper} 
        sx={{ 
          borderRadius: 2,
          boxShadow: 3,
          '& .MuiTableRow-root:hover': {
            backgroundColor: alpha(theme.palette.primary.main, 0.1),
          }
        }}
      >
        <Table size={isMobile ? "small" : "medium"}>
          <TableHead>
            <TableRow>
              <TableCell 
                onClick={() => handleSort('player_name')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                Player {sortField === 'player_name' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                onClick={() => handleSort('prop_type')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                Prop Type {sortField === 'prop_type' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('line')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                Line {sortField === 'line' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('prizepicks_odds')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                PrizePicks {sortField === 'prizepicks_odds' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('pinnacle_over')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                Pinnacle Over {sortField === 'pinnacle_over' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('pinnacle_under')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                Pinnacle Under {sortField === 'pinnacle_under' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('no_vig_over')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                No-Vig Over {sortField === 'no_vig_over' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell 
                align="right" 
                onClick={() => handleSort('no_vig_under')} 
                sx={{ cursor: 'pointer', fontWeight: 'bold' }}
              >
                No-Vig Under {sortField === 'no_vig_under' && (sortDirection === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />)}
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                Comparison
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAndSortedData?.map((prop, index) => (
              <TableRow key={index}>
                <TableCell>{prop.player_name}</TableCell>
                <TableCell>{prop.prop_type}</TableCell>
                <TableCell align="right">{prop.line}</TableCell>
                <TableCell align="right">{prop.prizepicks_odds}</TableCell>
                <TableCell align="right">{prop.pinnacle_over.toFixed(2)}</TableCell>
                <TableCell align="right">{prop.pinnacle_under.toFixed(2)}</TableCell>
                <TableCell align="right">{prop.no_vig_over.toFixed(2)}</TableCell>
                <TableCell align="right">{prop.no_vig_under.toFixed(2)}</TableCell>
                <TableCell align="center">
                  <OddsComparison 
                    prizepicks={prop.prizepicks_odds} 
                    pinnacleOver={prop.pinnacle_over} 
                    pinnacleUnder={prop.pinnacle_under} 
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}

function App() {
  return (
    <ThemeProvider theme={darkTheme}>
      <QueryClientProvider client={queryClient}>
        <Container maxWidth="lg">
          <Box sx={{ my: 4 }}>
            <Typography 
              variant="h3" 
              component="h1" 
              gutterBottom 
              align="center"
              sx={{ 
                fontWeight: 'bold',
                background: 'linear-gradient(45deg, #90caf9 30%, #f48fb1 90%)',
                backgroundClip: 'text',
                textFillColor: 'transparent',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              PrizePicks vs Pinnacle Odds
            </Typography>
            <Typography 
              variant="subtitle1" 
              align="center" 
              color="text.secondary" 
              paragraph
              sx={{ mb: 4 }}
            >
              Compare player props and find the best value
            </Typography>
            <PropsTable />
          </Box>
        </Container>
      </QueryClientProvider>
    </ThemeProvider>
  )
}

export default App
