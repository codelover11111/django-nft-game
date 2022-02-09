let currentAccount = null;
const onboardButton = document.getElementById('metamask_btn');
// const forwarderOrigin = 'http://localhost:8000';
let ether_price = 0;
let addy_price = 0;
let chainId = -1;
let rec_address = '';

const onClickConnect = async () => {
  try {
    // Will open the MetaMask UI
    // You should disable this button while the request is pending!
    await ethereum.request({ method: 'eth_requestAccounts' });
  } catch (error) {
    console.error(error);
  }
};

function handleAccountsChanged(accounts) {
  if (accounts.length === 0) {
    // MetaMask is locked or the user has not connected any accounts
    console.log('Please connect to MetaMask.');
    currentAccount = null;
    ConnectButtonInit(false);
  } else {
    currentAccount = accounts[0];
    ConnectButtonInit(true);
    console.log(111);
    // Do any other work!
    return true;
  }
}

function ConnectButtonInit(val){
  if (val)
  {
    onboardButton.innerHTML = '<span>Wallet Connected</span>';
    onboardButton.onclick = onClickConnect;
    onboardButton.disabled = false;
  }
  else
  {
    onboardButton.innerHTML = '<span>Connect Wallet</span>';
    onboardButton.onclick = onClickConnect;
    onboardButton.disabled = false;
  }
}

const initialize = () => {
  // Basic Actions Section
  const isMetaMaskInstalled = () => {
    const { ethereum } = window;
    return Boolean(ethereum && ethereum.isMetaMask);
  };

  const onboarding = new MetamaskOnboarding();
  // This will start the onboarding proccess
  const onClickInstall = () => {
    onboardButton.innerHTML = '<span>Installing...</span>';
    onboardButton.disabled = true;
    // On this object we have startOnboarding which will start the onboarding process for our end user
    onboarding.startOnboarding();
  };

  const MetaMaskClientCheck = () => {
    if (!isMetaMaskInstalled()) {
      onboardButton.innerHTML = '<span>Install MetaMask!</span>';
      onboardButton.onclick = onClickInstall;
      onboardButton.disabled = false;
    } else {
        try {
            currentAccount = ethereum.selectedAddress;
            console.log(currentAccount, "555");
            if (currentAccount === null)
                ConnectButtonInit(false);
            else
                ConnectButtonInit(true);
        } catch (e) {
            ConnectButtonInit(false);
        }
    }
  };
  MetaMaskClientCheck();
  /*const getAccountsButton = document.getElementById('getAccounts');
  const getAccountsResult = document.getElementById('getAccountsResult');
  getAccountsButton.addEventListener('click', async () => {
  // we use eth_accounts because it returns a list of addresses owned by us.
    const accounts = await ethereum.request({ method: 'eth_accounts' });
    // We take the first address in the array of addresses and display it
    getAccountsResult.innerHTML = accounts[0] || 'Not able to get accounts';
  });*/
};
window.addEventListener('DOMContentLoaded', initialize);
try
{
    ethereum.on('accountsChanged', (accounts) => {
      if (accounts == null || accounts.length <= 0)
      {
        currentAccount = null;
          ConnectButtonInit(false);
      }
      else
      {
        ConnectButtonInit(true);
        currentAccount = accounts[0];
        window.location.reload();
      }
    });

    ethereum.on('chainChanged', (_chainId) => {
        chainId = _chainId;
        window.location.reload();
    });


    ethereum.on('connect', (ConnectInfo) => {
      if (!ethereum.isConnected())
      {
          currentAccount = null;
        ConnectButtonInit(false);
        return;
      }
      ethereum._metamask.isUnlocked().then( (val) => {
          console.log('val ' + val);
        if (val)
        {
          ethereum
            .request({ method: 'eth_accounts' })
            .then(handleAccountsChanged)
            .catch((err) => {
              // Some unexpected error.
              // For backwards compatibility reasons, if no accounts are available,
              // eth_accounts will return an empty array.
              console.error(err);
              currentAccount = null;
              ConnectButtonInit(false);
              return;
          });
          console.log(222)
        }
        else
        {
            console.log(333);
            currentAccount = null;
          ConnectButtonInit(val);
        }
      }).catch(function(err) {
        console.log('then error : ', err); // then error :  Error: Error in then()
        ConnectButtonInit(false);
      });
    });
    ethereum.on('disconnect', (ProviderRpcError) => {
        console.log(444);
        currentAccount = null;
        ConnectButtonInit(false);
    });
} catch (e) {
    console.log(e.toString());
}

function onclick_deposit() {
    let net = $('#network_list').val();
    if (net === 'hrc') {
        onclick_deposit_hrc20_crown();
    }
    if (net === 'bsc') {
        onclick_deposit_bep20_crown();
    }
    if (net === 'erc') {
        onclick_deposit_erc20_crown();
    }
}
async function onclick_deposit_bep20_crown() {
    let d_am = $('#deposit_amount').val();
    d_am = parseFloat(d_am);
    if (isNaN(d_am)) {
        alert("Please write correct amount");return;
    }
    if (d_am <= 0) return;
    if (currentAccount === null || currentAccount === '')
    {
        alert('Please connect Metamask');
        return;
    }
    if (chainId <= 0) {
        chainId = await ethereum.request({method: 'eth_chainId'});
    }
    if (chainId <= 0) return;

    let ajax_result = null;
    $.ajax({
       type : "POST",
       url: "/user/get_binance_contract_data/",
       async: false,
       data: {"amount": d_am, "chain_id": chainId.toString()},
       success: function (res) {
            ajax_result = res;
       }
    });
    if (ajax_result['result'] !== 'success') {
        if(ajax_result['error_type'] === 'not_binance_chain') {
            alert(ajax_result['error_msg']);
        } else {
            alert('Failure!');
        }
        return;
    }
    const transactionParameters = {
      nonce: '0x00', // ignored by MetaMask
      to: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
      from: currentAccount, // must match user's active address.
      chainId: chainId.toString(),
      data: ajax_result['data'],
      // gas: ajax_result['gas'],
      // gasPrice: ajax_result['gasPrice'],
    };
    txHash = await ethereum.request({
      method: 'eth_sendTransaction',
      params: [transactionParameters],
    });

    let param = {
        'txhash': txHash, 'from_address':currentAccount, 'd_am': d_am, 'chain_id': chainId.toString(),
        'type': 'bsc'
    };
    $.ajax({
       type: 'POST',
       url: '/user/record_transaction/',
       data: param,
       success: function (payload) {
            if (payload['result'] === 'success') {
                alert("Success!");
                window.location.reload();
            } else {
                alert('Failure!');
            }
       }
    });
}

async function onclick_deposit_hrc20_crown() {
    let d_am = $("#deposit_amount").val();
    d_am = parseFloat(d_am);
    if (isNaN(d_am)) {
        alert("Please write correct amount");return;
    }
    if (d_am <= 0) return;
    if (currentAccount === null || currentAccount === '')
    {
        alert('Please connect Metamask');
        return;
    }
    if (chainId <= 0) {
        chainId = await ethereum.request({method: 'eth_chainId'});
    }
    if (chainId <= 0) return;

    let ajax_result = null;
    $.ajax({
       type : "POST",
       url: "/user/get_contract_data/",
       async: false,
       data: {"amount": d_am, "chain_id": chainId.toString()},
       success: function (res) {
            ajax_result = res;
       }
    });
    if (ajax_result['result'] !== 'success') {
        if(ajax_result['error_type'] === 'not_harmony_chain') {
            alert(ajax_result['error_msg']);
        } else {
            alert('Failure!');
        }
        return;
    }

    const transactionParameters = {
      nonce: '0x00', // ignored by MetaMask
      to: '0xa1a4ebdfb78893fa68b630da8247f4567211b64b',
      from: currentAccount, // must match user's active address.
      chainId: chainId.toString(),
      data: ajax_result['data'],
      // gas: ajax_result['gas'],
      // gasPrice: ajax_result['gasPrice'],
    };
    txHash = await ethereum.request({
      method: 'eth_sendTransaction',
      params: [transactionParameters],
    });

    let param = {
        'txhash': txHash, 'from_address':currentAccount, 'd_am': d_am, 'chain_id': chainId.toString(),
        'type': 'hrc'
    };
    $.ajax({
       type: 'POST',
       url: '/user/record_transaction/',
       data: param,
       success: function (payload) {
            if (payload['result'] === 'success') {
                alert("Success!");
                window.location.reload();
            } else {
                alert('Failure!');
            }
       }
    });
}

async function onclick_withdraw_crown() {
    let d_am = $('#withdraw_amount').val();
    d_am = parseFloat(d_am);
    if (isNaN(d_am)){
        alert('Please write correct amount');return;
    }
    if (d_am <= 0) return;

    if (chainId <= 0) {
        chainId = await ethereum.request({method: 'eth_chainId'});
    }
    if (chainId <= 0) return;
    let ajax_result = null;

    $.ajax({
        type: 'POST',
        url: '/user/withdraw/',
        async: false,
        data: {'amount': d_am, 'chain_id': chainId.toString(), 'player_account': currentAccount,
            'type': $('#network_list').val()
        },
        success: function (res) {
            ajax_result = res;
        }
    });
    if (ajax_result['result'] !== 'success') {
        if(ajax_result['error_type'] === 'not_harmony_chain') {
            alert(ajax_result['error_msg']);
        }
        if(ajax_result['error_type'] === 'transaction_error') {
            alert('Failure!');
        }
        if(ajax_result['error_type'] === 'balance_not_enough') {
            alert(ajax_result['error_msg']);
        }
        return;
    }
    alert("Success!");
    window.location.reload();

}

function onselect_network() {
    let net = $('#network_list').val();
    if (net === 'hrc') {
        $('#harmony_smcw_balance').css('display', 'block');
        $('#bsc_smcw_balance').css('display', 'none');
        $('#eth_smcw_balance').css('display', 'none');
    }
    if (net === 'erc') {
        $('#harmony_smcw_balance').css('display', 'none');
        $('#bsc_smcw_balance').css('display', 'none');
        $('#eth_smcw_balance').css('display', 'block');
    }
    if (net === 'bsc') {
        $('#harmony_smcw_balance').css('display', 'none');
        $('#bsc_smcw_balance').css('display', 'block');
        $('#eth_smcw_balance').css('display', 'none');
    }
}
function enable_deposit() {
    if ($('#deposit_mode').hasClass("active")) {
        return;
    }
    $('#deposit_mode').addClass('active');
    $('#withdraw_mode').removeClass('active');
    $('#deposit_section').css('display', 'block');
    $('#withdraw_section').css('display', 'none');
}
function enable_withdraw() {
    if ($('#withdraw_mode').hasClass("active")) {
        return;
    }
    $('#withdraw_mode').addClass('active');
    $('#deposit_mode').removeClass('active');
    $('#deposit_section').css('display', 'none');
    $('#withdraw_section').css('display', 'block');
}